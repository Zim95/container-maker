# Set default values if environment variables are not set
: ${server_threads:=10}
: ${address:="0.0.0.0"}
: ${port:=50052}
: ${use_ssl:=true}
: ${jupyter_notebook_ip:="0.0.0.0"}
: ${jupyter_notebook_port:=8889}

# run the grpc server
exec python app.py --server_threads="${server_threads}" --address="${address}" --port="${port}" --use_ssl="${use_ssl}"

# run the jupyter notebook
exec jupyter lab --no-browser --port="${jupyter_notebook_port}" --ip="${jupyter_notebook_ip}" --allow-root
