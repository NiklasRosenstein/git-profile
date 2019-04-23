# git-profile

A tiny command-line tool that allows you to override local repository
settings by switching profilef.

    $ git profile
    * default
      Work
    $ git profile Work
    Switched to profile "Work".

A profile can be created simply by adding the name of the profile to one
or more sections that should be overwritten when the profile is activated.

    [Work.user]
      email = "me@work.com"
      signingkey = 2SDASF9ASF8ASF9A

To revert the changes that a profile applied, simply do

    $ git profile default

### Vendored Libraries

* [`gitconfigparser.py`](https://github.com/looking-for-a-job/gitconfigparser.py)
  by looking-for-a-job @ GitHub

### Changelog

#### 1.0.0 (2019-04-23)

* Initial release

---

<p align="center">Copyright &copy; 2019 Niklas Rosenstein</p>
