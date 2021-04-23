# Web Scraping on BBC/VOA/DW/RFI

## Setup Tor and activate virtual environment
1. Use `sudo apt install tor` to install tor
2. Uncomment `ControlPort 9051` and `CookieAuthentication 1` in `/etc/tor/torrc`
3. Use `sudo chmod 644 /run/tor/control.authcookie`
4. Use `conda create -n newsdata python=3.7` to create a new environment
5. Use `conda activate newsdata` to activate the previously created environment

## Clone the project
You can clone the repository with `git clone https://github.com/Cirhuzalain/cdsdataset`
After cloning the project use `cd cdsdataset`

## Install Dependencies
Use `pip install -r requirements.txt` command

## Get document sample
Use `python main.py -s data.json -r 1 -p 32 -b 5` command

## Built with
* Python
* Requests
* Beautifulsoup
* Stem