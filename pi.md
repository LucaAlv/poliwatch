Your ongoing development workflow
After making and testing changes on the laptop:

git push origin main
ssh luca@poliwatch.local
cd /home/luca/apps/poliwatch
git pull --ff-only origin main
sudo systemctl start poliwatch-update.service

--ff-only is valuable on a deployment machine: it refuses to invent a merge commit if somebody accidentally edited the Pi’s checkout.