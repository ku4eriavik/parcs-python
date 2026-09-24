#!/usr/bin/env python3
import argparse
import os

from parcs_py import Config, parcs

parser = argparse.ArgumentParser(description='PARCS Python launcher...')
parser.add_argument('--node-role', choices=('master', 'worker'), default=os.getenv('PARCS_NODE_ROLE'),
                    help='Node role; defaults to PARCS_NODE_ROLE.')
parser.add_argument('--bind-host', default=os.getenv('PARCS_BIND_HOST', '0.0.0.0'),
                    help='Local interface address for HTTP and RPC listeners.')
parser.add_argument('-ip', '--advertise-host', dest='advertise_host', default=os.getenv('PARCS_ADVERTISE_HOST'),
                    help='Address advertised by a worker to the master.')
parser.add_argument('-port', '--port', dest='port', type=int, default=int(os.getenv('PARCS_HTTP_PORT', '8080')),
                    help='HTTP port; defaults to PARCS_HTTP_PORT or 8080.')
parser.add_argument('--rpc-port', type=int, default=int(os.getenv('PARCS_RPC_PORT', '9090')),
                    help='Pyro5 RPC port; defaults to PARCS_RPC_PORT or 9090.')
parser.add_argument('-master_ip', '--master-host', dest='master_host', default=os.getenv('PARCS_MASTER_HOST'),
                    help='Master address used by a worker.')
parser.add_argument('-master_port', '--master-port', dest='master_port', type=int,
                    default=int(os.getenv('PARCS_MASTER_PORT', '8080')),
                    help='Master HTTP port; defaults to PARCS_MASTER_PORT or 8080.')

args = parser.parse_args()
master = args.node_role == 'master' if args.node_role else args.master_host is None
if not master and not args.master_host:
    parser.error('worker nodes require --master-host or PARCS_MASTER_HOST')
if not master and not args.advertise_host:
    parser.error('worker nodes require --advertise-host or PARCS_ADVERTISE_HOST')
config = Config(
    ip=args.advertise_host,
    port=args.port,
    master_ip=None if master else args.master_host,
    master_port=args.master_port,
    bind_host=args.bind_host,
    rpc_port=args.rpc_port,
    master=master,
)

parcs.start(config)
