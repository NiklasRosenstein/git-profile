# nr.git-profile

A tiny command-line tool that allows you to override local repository
settings by enabling a profile.

    $ nr git-profile
    * none
      Work
    $ nr git-profile Work
    Switched to profile "Work".

A profile can be created simply by adding the name of the profile to one
or more sections that should be overwritten when the profile is activated.

    [Work.user]
      email = "nrosenstein@work.com"
      signingkey = 2SDASF9ASF8ASF9A

To revert the changes that a profile applied, simply do

    $ nr git-profile none

I recommend creating an alias in your `.gitconfig` so that you can write
`git profile` instead of `nr git-profile`.

    [alias]
      profile = !nr git-profile

---

<p align="center">Copyright &copy; 2018 Niklas Rosenstein</p>
