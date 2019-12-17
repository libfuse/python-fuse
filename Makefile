all: source manylinux

source:
	python3 setup.py sdist

manylinux:
	docker run --rm -it -e PLAT=manylinux2010_x86_64 -v $(PWD):/io:Z -w /io quay.io/pypa/manylinux2010_x86_64 bash -c "yum install -y fuse-devel && /opt/python/cp37-cp37m/bin/python setup.py bdist_wheel && auditwheel repair dist/*.whl"

clean:
	python3 setup.py clean --all
	rm -fr build dist fuse_python.egg-info wheelhouse
