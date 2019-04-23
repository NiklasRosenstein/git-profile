
import io
import re
import setuptools

with io.open('src/git_profile_command/__init__.py', encoding='utf8') as fp:
  version = re.search(r"__version__\s*=\s*'(.*)'", fp.read()).group(1)

with io.open('README.md', encoding='utf8') as fp:
  long_description = fp.read()

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
  packages = setuptools.find_packages('src'),
  package_dir = {'': 'src'},
  install_requires = ['nr.types>=2.0.0', 'six>=1.11.0'],
  entry_points = {
    'console_scripts': [
      'git-profile = git_profile_command:main'
    ]
  }
)
