import asyncio
from contextlib import contextmanager, ExitStack
from functools import partial
import multiprocessing
import os
import sys

import pytest

__all__ = ('starter',)


def _runner(target, args, kwargs, stdout_w, stderr_w):
    os.dup2(stdout_w.fileno(), 1)
    os.dup2(stderr_w.fileno(), 2)
    target(*args, **kwargs)


class _TeeSubprocessStreamProtocol(
        asyncio.subprocess.SubprocessStreamProtocol):

    def pipe_data_received(self, fd, data):
        if fd == 1:
            stream = sys.stdout.buffer
        elif fd == 2:
            stream = sys.stderr.buffer
        else:
            stream = None
        if stream is not None:
            stream.write(data)
        super().pipe_data_received(fd, data)


class _TeeStreamReaderProtocol(
        asyncio.streams.StreamReaderProtocol):

    def __init__(self, *args, tee=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._tee = tee.buffer

    def data_received(self, data):
        if self._tee is not None:
            self._tee.write(data)
        super().data_received(data)


async def _read_until_magic_words(magic_words, timeout, *streams):
    done, _ = await asyncio.wait(
        [s.readuntil(magic_words) for s in streams],
        return_when=asyncio.FIRST_COMPLETED,
        timeout=timeout)
    if not done:
        raise TimeoutError(
            'The magic words {!r} were not seen in any of the streams '
            'before {} seconds elapsed.'.format(magic_words, timeout))


@contextmanager
def _exec_process_context(args, magic_words, timeout):
    loop = asyncio.get_event_loop()
    factory = partial(
        _TeeSubprocessStreamProtocol,
        limit=asyncio.streams._DEFAULT_LIMIT,
        loop=loop)
    transport, protocol = loop.run_until_complete(
        loop.subprocess_exec(
            factory, *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE))
    proc = asyncio.subprocess.Process(transport, protocol, loop)
    try:
        loop.run_until_complete(
            _read_until_magic_words(
                magic_words, timeout, proc.stdout, proc.stderr))
        yield
    finally:
        proc.terminate()


async def _python_process_wait(r_pipes, loop, magic_words, timeout):
    with ExitStack() as stack:
        readers = []
        for r_pipe, stdstream in zip(r_pipes, [sys.stdout, sys.stderr]):
            reader = asyncio.StreamReader(loop=loop)
            readers.append(reader)
            factory = partial(
                _TeeStreamReaderProtocol, reader, loop=loop, tee=stdstream)
            file = stack.enter_context(open(r_pipe.fileno(), 'rb'))
            await loop.connect_read_pipe(factory, file)
        await _read_until_magic_words(magic_words, timeout, *readers)


@pytest.fixture
def starter(capsys):
    """Fixture for starting subprocesses."""

    @contextmanager
    def _python_process_context(target, args, kwargs, magic_words, timeout):
        with capsys.disabled():
            r_pipes, w_pipes = zip(*(multiprocessing.Pipe() for _ in range(2)))
            proc = multiprocessing.Process(
                target=_runner, args=(target, args, kwargs, *w_pipes))
            proc.start()
        try:
            loop = asyncio.get_event_loop()
            loop.run_until_complete(
                _python_process_wait(r_pipes, loop, magic_words, timeout))
            yield
        finally:
            proc.terminate()
            proc.join()

    with ExitStack() as stack:

        class Starter:

            @staticmethod
            def exec_process(*args, magic_words=None, timeout=1):
                stack.enter_context(
                    _exec_process_context(*args, magic_words, timeout))

            @staticmethod
            def python_process(target, args=(), kwargs={},
                               magic_words=None, timeout=1):
                stack.enter_context(
                    _python_process_context(
                        target, args, kwargs, magic_words, timeout))

        yield Starter
