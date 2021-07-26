#!/bin/bash
socat -d -d PTY,raw,echo=0,link=./tty-write PTY,raw,echo=1,link=./tty-read

