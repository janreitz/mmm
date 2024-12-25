sudo ln -s ~/mmm/systemd/marta.service /etc/systemd/system/marta.service
sudo ln -s ~/mmm/systemd/power-button-daemon.service /etc/systemd/system/power-button-daemon.service
sudo ln -s ~/mmm/scripts/cut_power.sh /lib/systemd/system-shutdown/cut_power.sh
sudo ln -s ~/mmm/scripts/power_button_daemon.py /usr/local/bin/power_button_daemon.py

sudo systemctl daemon-reload
sudo systemctl enable marta
sudo systemctl enable power-button-daemon
