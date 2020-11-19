# git-profile

This command-line tool allows you to define a set of configuration profiles that can be applied on
a per-repository basis. The main use case is to swap the user details and signing key, but it's
not limited to just that.

## Installation

We recommend installing the tool with Pipx.

    $ pipx install git-profile

## Configuration

In `~/.gitconfig`, prefixing section names with `<Profile>.` assigns them to the specified profile.
Git-profile can use that information to determine which profiles there are and what configuration
is associated with it.

Example:

```ini
[Work.user]
  email = "me@work.com"
  signingkey = DEADBEEFDEADBEEF
```

## Usage

Run `git profile` to list available profiles. The current profile will be marked with a star. Note
that the `default` profile is always present and represents your normal Git configuration without
profile overrides.

    $ git profile
    * default
      Work

With `git profile <Profile>` you can switch to the specified profile.

    $ git profile Work
    Switched to profile "Work".

The changes will be applied to `.git/config` of the current repository.

You can add the `--diff` option to print a diff of the applied config changes.

## FAQ

### How do I avoid accidentally forgetting to switch my profile after checking out a repository?

You can leave the `[user]` section of your default configuration empty. That way Git will prompt
you to configure it when trying to commit. Simply run `git profile <Profile>` after that and
commit again.

## Vendored Libraries

* [`gitconfigparser.py`](https://github.com/looking-for-a-job/gitconfigparser.py)
  by looking-for-a-job @ GitHub

---

<p align="center">Copyright &copy; 2012 Niklas Rosenstein</p>
