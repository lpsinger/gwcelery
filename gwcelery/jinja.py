from jinja2 import Environment, PackageLoader, select_autoescape

__all__ = ('env',)

env = Environment(loader=PackageLoader(__name__, 'templates'),
                  autoescape=select_autoescape,
                  trim_blocks=True)
