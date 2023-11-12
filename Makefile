all: source manylinux

source:
	python3 setup.py sdist

manylinux:
	docker run --rm -it -e PLAT=manylinux_2_28 -v $(PWD):/io -w /io quay.io/pypa/manylinux_2_28_x86_64 bash -c "yum install -y fuse-devel && /opt/python/cp312-cp312/bin/python setup.py bdist_wheel && auditwheel repair dist/*.whl"

clean:
	python3 setup.py clean --all
	rm -fr build dist fuse_python.egg-info wheelhouse
