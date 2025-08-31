#!/bin/bash
dest_dir=$1
# script_dir is the directory where this script stays
script_dir=$(pwd)
mkdir -p $dest_dir
for provider in $(ls ~/.saidata-gen/cache); do
    $script_dir/list_packages.py $provider > $dest_dir/$provider.txt
done