#!/bin/sh -e

# Works only in the hg repo incarnation of the source tree.
# Mercurial, docutils, setuptools needs to be installed.

if ! hg log -r tip --template '{desc}' |  grep -q 'Added tag .* for changeset'; then
    echo "you forgot to tag before release!" 2>&1
    exit 1
fi

hg_tag="`hg tags | awk '{if ($0 !~ /^tip /) { print $1; exit; }}'`"
setupdotpy_version="`python setup.py -V`"
if ! [ "$hg_tag" = "$setupdotpy_version" ]; then
    echo "HG tag '$hg_tag' doesn't match reported program version '$setupdotpy_version'" 2>&1
    exit 1
fi

hg log --style util/fusepychangelog.tmpl | grep -v '^TAGS: tip$' > Changelog
rst2html.py --stylesheet util/voidspace-fusepy.css README.new_fusepy_api > README.new_fusepy_api.html
python setup.py sdist
python setup.py bdist_egg
