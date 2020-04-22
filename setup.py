# automatically created by shore 0.0.8

import io
import re
import setuptools
import sys

with io.open('src/git_profile_command/__init__.py', encoding='utf8') as fp:
  version = re.search(r"__version__\s*=\s*'(.*)'", fp.read()).group(1)

with io.open('README.md', encoding='utf8') as fp:
  long_description = fp.read()

requirements = ['nr.databind.core >=0.0.6,<0.1.0', 'nr.databind.json >=0.0.4,<0.1.0', 'six >=1.11.0,<2.0.0']

setuptools.setup(
  name = 'git-profile',
  version = version,
  author = 'Niklas Rosenstein',
  author_email = 'rosensteinniklas@gmail.com',
  description = 'Easily switch between Git configurations on a per-repository basis.',
  long_description = long_description,
  long_description_content_type = 'text/markdown',
  url = 'https://github.com/NiklasRosenstein/git-profile',
  license = 'MIT',
  packages = setuptools.find_packages('src', ['test', 'test.*', 'docs', 'docs.*']),
  package_dir = {'': 'src'},
  include_package_data = True,
  install_requires = requirements,
  extras_require = {},
  tests_require = [],
  python_requires = None, # TODO: '>=3.4,<4.0.0',
  data_files = [],
  entry_points = {
    'console_scripts': [
      'git-profile = git_profile_command:main',
    ]
  },
  cmdclass = {},
  keywords = [],
  classifiers = [],
)
