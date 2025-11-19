source_dir="deliverables"

# Set the destination directory (where to copy the .db files)
dest_dir="/var/lib/docker/volumes/cnect-monitor-data/_data/"


# Find all .db files recursively and copy them to the destination directory
find "/home/ubuntu/connect-monitor/deliverables" -type f -name "*.db" -exec cp {} "/var/lib/docker/volumes/cnect-monitor-data/_data/" \;