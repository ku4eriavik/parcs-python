import importlib.util
import json
import logging
import requests
import time

from abc import abstractmethod
from Pyro5.api import Daemon
from threading import Thread

from .file_utils import get_solution_path
from .node_info import get_node_info_for_current_machine
from .node_link import NodeLink


log = None


class Node:
    def __init__(self, conf):
        self.conf = conf
        self.info = get_node_info_for_current_machine()

    @abstractmethod
    def is_master_node(self):
        pass

    @staticmethod
    def create_node(conf):
        if conf.master:
            return MasterNode(conf)
        else:
            node = WorkerNode(conf)
            return node


class WorkerNode(Node):
    def __init__(self, conf):
        Node.__init__(self, conf)
        global log
        log = logging.getLogger('Worker Node')
        self.rpc_thread = None
        self.master = NodeLink(conf.master_ip, conf.master_port)
        self.connected = False
        log.info('Started on %s:%d; Job directory: %s.', conf.ip, conf.port, conf.job_home)
        self.reconnector = MasterReconnector(self)
        self.reconnector.start()

    def is_master_node(self):
        return False

    def register_on_master(self):
        data = {'ip': self.conf.ip, 'port': self.conf.port,
                'info': {'cpu': self.info.cpu, 'ram': self.info.ram}}
        headers = {'Content-type': 'application/json', 'Accept': 'text/plain'}
        try:
            r = requests.post('http://%s:%s/api/internal/worker' % (self.master.ip, self.master.port),
                              data=json.dumps(data), headers=headers)
            if r.status_code == 200:
                self.connected = True
                log.info('Registered to master on %s:%d.',
                         self.conf.master_ip, self.conf.master_port)
            else:
                self.connected = False
                log.warning('Unable to register to master on %s:%d.', self.conf.master_ip, self.conf.master_port)
        except Exception as e:
            self.connected = False
            log.warning('Unable to register to master on %s:%d because of %s.', self.conf.master_ip,
                        self.conf.master_port, str(e))

    def connection_with_master_lost(self):
        self.connected = False
        log.warning('Connection with master %s:%d lost.', self.master.ip, self.master.port)

    def start_rpc(self, job_id):
        self.stop_rpc()
        self.rpc_thread = RPCThread(
            self.conf.bind_host,
            self.conf.ip,
            self.conf.rpc_port,
            job_id,
            self.conf.job_home,
        )
        uri = self.rpc_thread.register_algorithm_module()
        if uri is None:
            self.rpc_thread.stop()
            self.rpc_thread = None
            return None
        self.rpc_thread.start()
        log.info("Started RPC for %d job on %s.", job_id, uri)
        return uri

    def stop_rpc(self):
        if self.rpc_thread is None:
            return
        self.rpc_thread.stop()
        log.info("Stopped RPC for %d job.", self.rpc_thread.job_id)
        self.rpc_thread = None


class MasterReconnector(Thread):
    def __init__(self, worker_node):
        super(MasterReconnector, self).__init__()
        self.daemon = True
        self.worker_node = worker_node

    def run(self):
        while True:
            if self.worker_node.connected:
                try:
                    response = requests.get('http://%s:%s/api/internal/heartbeat' % (
                        self.worker_node.master.ip, self.worker_node.master.port), timeout=5)
                    if response.status_code != 200:
                        self.worker_node.connection_with_master_lost()
                except requests.RequestException:
                    self.worker_node.connection_with_master_lost()
            else:
                self.worker_node.register_on_master()
            time.sleep(5)


class MasterNode(Node):
    def __init__(self, conf):
        Node.__init__(self, conf)
        global log
        log = logging.getLogger('Master Node')
        self.jobs = []
        self.workers = []
        log.info('Started on %s:%d; Job directory: %s.', conf.ip, conf.port,
                 conf.job_home)
        self.heartbeat = Heartbeat(self)
        self.heartbeat.start()

    def is_master_node(self):
        return True

    def register_worker(self, node_link):
        if not any(link.ip == node_link.ip and link.port == node_link.port for link in self.workers):
            self.workers.append(node_link)
            ret = True
        else:
            log.warning('Unable to register node %s:%d because it is already registered.', node_link.ip, node_link.port)
            ret = False
        return ret

    def find_worker(self, worker_id):
        return next((worker for worker in self.workers if worker.id == worker_id), None)

    def delete_worker(self, worker_id):
        prev_len = len(self.workers)
        self.workers = [worker for worker in self.workers if worker.id != worker_id]
        return prev_len != len(self.workers)

    def abort_job(self, job_id):
        result = False
        for j in self.jobs:
            if j.id == job_id:
                j.abort_job()
                result = True
        return result

    def add_job(self, job):
        self.jobs.append(job)
        log.info("Job was added.")

    def find_job(self, job_id):
        return next((job for job in self.jobs if job.id == job_id), None)


class Heartbeat(Thread):
    def __init__(self, master_node):
        super(Heartbeat, self).__init__()
        self.daemon = True
        self.master_node = master_node
        self.log = logging.getLogger('Heartbeat')

    def run(self):
        while True:
            time.sleep(5)
            self.log.debug('%d workers is about to check.', len(self.master_node.workers))
            dead_workers = []
            for worker in self.master_node.workers:
                try:
                    response = requests.get('http://%s:%s/api/internal/heartbeat' % (worker.ip, worker.port))
                    if response.status_code != 200:
                        dead_workers.append(worker.id)
                except requests.RequestException:
                    dead_workers.append(worker.id)
            if len(dead_workers) == 0:
                self.log.debug('All workers alive.')
            else:
                self.log.warning('%d workers are dead.', len(dead_workers))
            for dead_worker in dead_workers:
                self.master_node.delete_worker(dead_worker)


class RPCThread(Thread):
    log = logging.getLogger('RPC Thread')

    def __init__(self, bind_host, advertise_host, port, job_id, job_home):
        super(RPCThread, self).__init__()
        self.daemon = True
        self.job_id = job_id
        self.job_home = job_home
        try:
            self.pyro_daemon = Daemon(
                host=bind_host,
                port=port,
                nathost=advertise_host,
                natport=port,
            )
            RPCThread.log.info('Pyro5 daemon created successfully.')
        except Exception:
            self.pyro_daemon = None
            RPCThread.log.exception('Unable to create Pyro5 daemon.')

    def register_algorithm_module(self):
        if not self.pyro_daemon:
            return None
        try:
            module_name = 'solver_module_%d' % self.job_id
            module_spec = importlib.util.spec_from_file_location(
                module_name, get_solution_path(self.job_home, self.job_id)
            )
            if module_spec is None or module_spec.loader is None:
                raise ImportError('Unable to load solver module specification.')
            algorithm_module = importlib.util.module_from_spec(module_spec)
            module_spec.loader.exec_module(algorithm_module)
            solver = algorithm_module.Solver()
            uri = self.pyro_daemon.register(solver)
            RPCThread.log.info("Algorithm module registered on %s.", uri)
            return uri
        except Exception:
            RPCThread.log.exception('Unable to create algorithm module or register it.')
            return None

    def run(self):
        try:
            self.pyro_daemon.requestLoop()
        except Exception:
            log.exception('Pyro5 RPC request loop failed.')

    def stop(self):
        if self.pyro_daemon:
            self.pyro_daemon.shutdown()
