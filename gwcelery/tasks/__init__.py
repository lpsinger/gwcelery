"""All Celery tasks are declared in submodules of this module."""


def _import_all_submodules(module=vars()):
    import importlib
    import pkgutil

    try:
        path = module['__path__']
    except KeyError:
        # not a package, does not have submodules
        return
    for _, name, _ in pkgutil.iter_modules(path):
        submodule = importlib.import_module('.' + name, module['__name__'])
        module[name] = submodule
        _import_all_submodules(vars(submodule))


# Recursively import all submodules.
_import_all_submodules()
