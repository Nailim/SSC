# set some variables
BLDDIR := build

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
	mkdir $(BLDDIR)
	
ifeq ($(DETECTED_OS),Linux) 
	$(MAKE) transpile_linux
	$(MAKE) compile_linux
else
	$(error "Not yet supported!")
endif



transpile_linux: SSC/ssc.py
	cython3 --embed -3 SSC/ssc.py -o build/ssc.c

transpile_darvin: SSC/ssc.py
	cython3 --embed -3 SSC/ssc.py -o build/ssc.c

transpile_windows: SSC\ssc.py
	cython3 --embed -3 SSC\ssc.py -o build\ssc.c



compile_linux:
	gcc -static -o build/ssc build/ssc.c -Os -I /usr/include/python3.8 $(pkg-config --libs --cflags python3) -lm -lutil -ldl -lz -lexpat -lpthread -lc
#	gcc -static -o build/ssc build/ssc.c -Os -I /usr/include/python3.8 -lpython3.8 -lpthread -lm -lutil -ldl

compile_darvin:
	gcc -o ssc ssc.c -Os -I /usr/include/python3.8 -lpython3.8 -lpthread -lm -lutil -ldl

compile_windows:
	gcc -o ssc ssc.c -Os -I /usr/include/python3.8 -lpython3.8 -lpthread -lm -lutil -ldl



clean:
	rm -r -f $(BLDDIR)

