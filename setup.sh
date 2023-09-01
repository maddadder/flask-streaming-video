python3 -m venv --system-site-packages ./venv
source ./venv/bin/activate  # sh, bash, or zsh
pip install --upgrade pip
#pip list  # show packages installed within the virtual environment
pip install -r requirements.txt
source ./venv/bin/activate
python app.py


# To Deploy:
docker-compose build
docker push 192.168.1.151:32000/flask-streaming-video:1.0.130
helm upgrade flask-streaming-video ./chart

# To access
kubectl port-forward -n kube-system service/kubernetes-dashboard 10443:443
