# set some variables
BLDDIR := bundle

# what are we running on
ifeq ($(OS),Windows_NT) 
	DETECTED_OS := Windows
else
	DETECTED_OS := $(shell sh -c 'uname 2>/dev/null || echo Unknown')
endif



all: run



run:
	cd SSC; python3 ssc.py



build:
	mkdir -p $(BLDDIR)
	
ifeq ($(DETECTED_OS),Linux) 
	$(MAKE) bundle_linux
else ifeq ($(DETECTED_OS),Darwin) 
	$(MAKE) bundle_darvin
else ifeq ($(DETECTED_OS),Windows) 
	$(MAKE) bundle_windows
else
	$(error "Not yet supported!")
endif



bundle_linux: SSC/ssc.py
	pyinstaller --workpath bundle/build --distpath bundle/dist --clean --onefile --name ssc_linux SSC/ssc.py

bundle_darvin: SSC/ssc.py
	pyinstaller --workpath bundle/build --distpath bundle/dist --clean --onefile --name ssc_darvin SSC/ssc.py

bundle_windows: SSC\ssc.py
	pyinstaller --workpath bundle\build --distpath bundle\dist --clean --onefile --name ssc_windows SSC\ssc.py



clean:
	rm -r -f $(BLDDIR)
	rm -r -f SSC/__pycache__

