# Server setup

Contact sandrino.costantini@ext.ec.europa.eu or yves.vanderrusten@ec.europa.eu for assistance.

### Prototype Setup

![Memory Screenshot](figures/current_system.png)


#### SSH access to EC2 instance


After logging into your AWS webspace via the AWS Client in the EC Store, you can ssh into the EC2 instace using:

```ssh -o "IdentitiesOnly=yes" -i D:\path\to\private\key ubuntu@10.178.27.214```

where ```D:\path\to\private\key``` needs to be replaced with the private key which belongs to the public key stored on the server. If you do not have a private key yet, you need to generate a new one and send the corresponding public key to Sandrino to get access to the server. The server is running between 7:30am and 10:30pm from Monday to Friday. 


#### File locations on the EC2 instance

- The EFMo repo is located at ```\home\ubuntu\connect-monitor```.
- The databases for the metabse dashboard are located at ```/var/lib/docker/volumes/cnect-monitor-data/_data/```


#### Crontab

Crontab manages the commands which are scheduled to run at rboot or at certain intervals on the server. The config file with thescheduling instructions can be edited using the command ```crontab -e```.

It should contain 

```
@reboot tmux new-session -d -s efmo "cd /home/ubuntu/connect-monitor && pipenv run python scheduler.py
```

This command launches a temux instance with the scheduler after every reboot. Temux is a container for running commands which keeps running even if you log out of the server. You can check whether there is a container running by typing ```tmux ls``` and access it using ```temux attach```. In order to leave the container, press ```CTRL+b``` and then ```d``` for "detach".

Further the **root crontab** (```sudo crontab -e```) should contain:

```
0 7 * * * find "/home/ubuntu/connect-monitor/deliverables" -type f -name "*.db" -exec cp {} "/var/lib/docker/volumes/cnect-monitor-data/_data/" \;
```

This command copies all the processed data (the databases in the deliverables folder of the repo) to the folder that can be accessed by the metabase dashboard. This step is important for updating the dashboard data. The update will not be invisible immedeitaley as metabase rescans the databases only every hour or so. 



### Possible future setup

![Memory Screenshot](figures/future_system.png)





## Server specs


Please note that the server should have at least 16GB of memory and a SWAP of at least 32GB for stable functionality.

![Memory Screenshot](figures/screenshot_memory.png)



