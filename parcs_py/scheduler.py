import importlib.util
import logging
import requests
import traceback
import time

from Pyro5.api import Proxy
from threading import Thread

from .file_utils import get_input_path, get_output_path, get_solution_path


class SolutionThread(Thread):
    NOT_STARTED = 1
    STARTED = 2
    SUCCESSFULLY_FINISHED = 3
    FAILURE_FINISHED = 4
    TERMINATED = 5

    def __init__(self, solver, job_id):
        super(SolutionThread, self).__init__()
        self.daemon = True
        self.solver = solver
        self.job_id = job_id
        self.status = SolutionThread.NOT_STARTED
        self.status_message = None

    def run(self):
        log.info("Solution thread started with %d job.", self.job_id)
        self.status = SolutionThread.STARTED
        try:
            for worker in getattr(self.solver, 'workers', []):
                worker._pyroClaimOwnership()
            self.solver.solve()
            self.status = SolutionThread.SUCCESSFULLY_FINISHED
            if not self.is_terminated():
                log.info("Solution thread successfully finished with %d job.", self.job_id)
        except Exception as e:
            self.status = SolutionThread.FAILURE_FINISHED
            self.status_message = str(e)
            log.warning('Solution thread finished with %d job because of an error in the solution file: %s.', self.job_id, str(e))
            traceback.print_exc()
        finally:
            for worker in getattr(self.solver, 'workers', []):
                worker._pyroRelease()

    def terminate(self):
        log.info("Solution thread terminated with %d job.", self.job_id)
        self.status = SolutionThread.TERMINATED

    def is_finished(self):
        return self.status == SolutionThread.TERMINATED or \
               self.status == SolutionThread.SUCCESSFULLY_FINISHED or \
               self.status == SolutionThread.FAILURE_FINISHED

    def is_terminated(self):
        return self.status == SolutionThread.TERMINATED


class NoWorkersException(Exception):
    def __init__(self):
        super(NoWorkersException, self).__init__()
        self.message = 'Unable to find workers.'


class Scheduler(Thread):
    def __init__(self, master, scheduled_jobs):
        super(Scheduler, self).__init__()
        self.daemon = True
        self.job_home = master.conf.job_home
        self.master = master
        self.scheduled_jobs = scheduled_jobs
        self.current_job = None
        self.executor = None

    def run(self):
        while True:
            self.current_job = self.scheduled_jobs.get()
            if self.current_job.aborted:
                self.current_job.abort_job()
                continue
            job_id = self.current_job.id
            log.info('Job %d enqueued.' % job_id)
            selected_workers = []
            try:
                self.current_job.start_job()
                rpc_workers, selected_workers = self.init_workers(job_id)

                if len(rpc_workers) == 0:
                    raise NoWorkersException()

                solution_module_path = get_solution_path(self.job_home, job_id)
                module_name = 'solver_module_%d' % job_id
                module_spec = importlib.util.spec_from_file_location(module_name, solution_module_path)
                if module_spec is None or module_spec.loader is None:
                    raise ImportError('Unable to load solver module specification.')
                solution_module = importlib.util.module_from_spec(module_spec)
                module_spec.loader.exec_module(solution_module)
                log.info('Loaded solution from %s.' % solution_module_path)

                solver = solution_module.Solver(rpc_workers, get_input_path(self.job_home, job_id),
                                                get_output_path(self.job_home, job_id))
                self.executor = SolutionThread(solver, job_id)
                self.executor.start()
                while not self.executor.is_finished():
                    if self.current_job.aborted:
                        self.executor.terminate()
                    else:
                        time.sleep(1)
                if self.executor.is_terminated():
                    self.current_job.abort_job()
                else:
                    if self.executor.status == SolutionThread.FAILURE_FINISHED:
                        self.current_job.end_job(True, self.executor.status_message)
                    else:
                        self.current_job.end_job()
            except Exception as e:
                self.current_job.end_job(True, str(e))
            finally:
                self.destroy_workers(selected_workers, job_id)
                self.current_job = None
                self.executor = None

    def init_workers(self, job_id):
        try:
            log.info('Starting workers...')
            active_workers = []
            workers_rpc_uris = []
            for worker in (worker for worker in self.master.workers if worker.enabled):
                with open(get_solution_path(self.job_home, job_id), 'rb') as solution_file:
                    response = requests.post(
                        'http://{}:{}/api/internal/job'.format(worker.ip, worker.port),
                        files={'solution': solution_file},
                        data={'job_id': job_id}
                    )
                if response.status_code == 200:
                    uri = response.json()['uri']
                    workers_rpc_uris.append(uri)
                    active_workers.append(worker)
                else:
                    log.warning('Unable to run RPC on %s:%d.', worker.ip, worker.port)
            log.debug('Obtained RPC urls: %s', workers_rpc_uris)
            rpc_workers = []
            for uri in workers_rpc_uris:
                rpc_workers.append(Proxy(uri))
            log.info('Started %d workers.', len(rpc_workers))
            return rpc_workers, active_workers
        except Exception:
            log.exception('Unable to initialize workers for job %d.', job_id)
            return [], []

    def destroy_workers(self, selected_workers, job_id):
        if len(selected_workers) == 0:
            return
        log.info('Stopping %d workers.' % len(selected_workers))
        for worker in selected_workers:
            response = requests.delete(
                    'http://%s:%d/api/internal/rpc/%d' % (worker.ip, worker.port, job_id))
            if response.status_code == 200:
                log.debug('RPC server on %s stopped.', worker.ip)
            else:
                log.warning('Unable to stop RPC server on %s.', worker.ip)
        log.info('%d workers where stopped.' % len(selected_workers))


log = logging.getLogger('Job Scheduler')
