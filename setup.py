
import setuptools
import io

with io.open('README.md', encoding='utf8') as fp:
  long_description = fp.read()

setuptools.setup(
  name = 'nr.git-profile',
  version = '1.1.0',
  author = 'Niklas Rosenstein',
  author_email = 'rosensteinniklas@gmail.com',
  description = 'Easily switch between Git configurations on a per-repository basis.',
  long_description = long_description,
  long_description_content_type = 'text/markdown',
  url = 'https://github.com/NiklasRosenstein/python-nr/tree/master/nr.git-profile',
  license = 'MIT',
  packages = setuptools.find_packages('src'),
  package_dir = {'': 'src'},
  namespace_packages = ['nr'],
  install_requires = [
    'nr.types>=2.0.0',
    'six>=1.11.0'
  ],
  entry_points = {
    'nr.cli.commands': [
      'git-profile = nr.git_profile:main'
    ]
  }
)
