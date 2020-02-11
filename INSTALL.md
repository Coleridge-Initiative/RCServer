# GCE VM Installation and Deployment Recipes


## Running as `root`
```
sudo bash
apt-get update

apt-get install emacs25-nox lynx
apt-get install virtualenv python-pip python-dev nginx

exit
```

# then install Anaconda <https://www.anaconda.com/distribution/>


## Running as `user`
```
cd
virtualenv -p /home/ceteri/anaconda3/bin/python3 ~/venv
source ~/venv/bin/activate

git clone https://github.com/Coleridge-Initiative/RCServer.git
cd RCServer
pip install -r requirements.txt
```


## Required environment settings
```
export FLASK_CONFIG="flask.cfg"
export GOOGLE_APPLICATION_CREDENTIALS="goog_api_key.json"

source ~/venv/bin/activate
```


## Initial deployment as `root`
```
sudo bash

cp etc/richcontext.service /etc/systemd/system/richcontext.service

systemctl daemon-reload
systemctl start richcontext
systemctl enable richcontext

cp etc/nginx.conf /etc/nginx
cp etc/richcontext.nginx /etc/nginx/sites-available/richcontext
ln -s /etc/nginx/sites-available/richcontext /etc/nginx/sites-enabled/richcontext

nginx -t
systemctl restart nginx

exit
```


## Generating an SSL certificate

Based on <https://certbot.eff.org/lets-encrypt/ubuntuxenial-nginx>
for Ubuntu 16.04

```
sudo bash

# add Certbot PPA
apt-get update
apt-get install software-properties-common
add-apt-repository universe
add-apt-repository ppa:certbot/certbot
apt-get update

# get a certificate
certbot certonly --nginx

exit
```
