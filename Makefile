all: source manylinux

PYTHON := python3
POLICY := manylinux_2_28
PLATFORM := x86_64
TAGS := cp312-cp312

source:
	python3 setup.py sdist

build:
	python3 setup.py build

manylinux:
	docker run --rm -v $(PWD):/io -w /io quay.io/pypa/$(POLICY)_$(PLATFORM) \
	    make build-wheels \
            POLICY=$(POLICY) PLATFORM=$(PLATFORM) TAGS="$(TAGS)"

build-wheels:
	yum install -y fuse-devel
	$(foreach tag,$(TAGS),$(MAKE) build-wheel TAG=$(tag) PATH="/opt/python/$(tag)/bin:$(PATH)";)

build-wheel:
	$(PYTHON) -m build --wheel --outdir dist-$(POLICY)-$(PLATFORM)-$(TAG)
	auditwheel repair dist-$(POLICY)-$(PLATFORM)-$(TAG)/*.whl

clean:
	$(PYTHON) setup.py clean --all
	rm -fr build dist dist-* fuse_python.egg-info wheelhouse

.PHONY: build
