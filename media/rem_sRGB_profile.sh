#!/bin/bash
find . -name '*.png' -exec exiftool -overwrite_original -all= {} \;
