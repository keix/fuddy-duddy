CC ?= cc
CFLAGS ?= -Wall -Wextra -Werror -O2

BINS = tracer fixtures/story fixtures/block

all: $(BINS)

tracer: tracer.c
	$(CC) $(CFLAGS) -o $@ $<

fixtures/story: fixtures/story.c
	$(CC) $(CFLAGS) -o $@ $<

fixtures/block: fixtures/block.c
	$(CC) $(CFLAGS) -o $@ $<

clean:
	rm -f $(BINS)

.PHONY: all clean
