#!/bin/sh -e

# Works only in the hg repo incarnation of the source tree.
# Mercurial, docutils, setuptools needs to be installed.

setupdotpy_version=`python setup.py -V`

# Finding out Mercurial cset until which we want to log
hgid=`hg id | awk '{print $1}'`
if echo $hgid | grep -q '+$'; then
    echo "you have outstanding changes, don't make a release" >&2
    exit 1
fi
hgrev=`hg log --template '{node|short} {rev}\n' | awk "{if (\\$1 ~ /$hgid/) { print \\$2 }}"`
hgtiprev=`hg log --template '{rev}' -r tip`
if ! [ $hgrev -eq $hgtiprev ]; then
    (echo "*************"
     echo "Warning: you are making a release from an older state of the code!"
     echo "*************") >&2
fi
if hg log --template '{tags}' -r $hgid | egrep -q "(^| )$setupdotpy_version($| )"; then
    log_to=$hgid
elif [ $hgrev -gt 0 ] &&
     hg log --template '{desc}' -r $hgid |  grep -q "Added tag $setupdotpy_version for changeset" &&
     hg log --template '{tags}' -r $(($hgrev - 1)) | egrep -q "(^| )$setupdotpy_version($| )"; then
    log_to=$(($hgrev - 1))
else
    echo "HG tag '$hg_tag' doesn't match reported program version '$setupdotpy_version'" >&2
    exit 1
fi

hg log --style util/fusepychangelog.tmpl -r $log_to:0 > Changelog
rst2html.py --stylesheet util/voidspace-fusepy.css README.new_fusepy_api > README.new_fusepy_api.html
{ hg manif | grep -v '^\.' | sed 's/^[0-9]\{3,\} \+\(.\+\)$/\1/' ; echo Changelog ; echo README.new_fusepy_api.html ; } | sed 's/^/include /' > MANIFEST.in
python setup.py sdist
python setup.py bdist_egg
