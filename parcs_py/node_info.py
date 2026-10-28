from cpuinfo import get_cpu_info


class NodeInfo:
    def __init__(self, cpu, ram):
        self.cpu = cpu
        self.ram = ram

    def serialize(self):
        return {'cpu': self.cpu, 'ram': self.ram}


def get_node_info_for_current_machine():
    # TODO
    return NodeInfo(get_cpu_info().get('brand_raw', 'Unknown CPU'), '4 GB')


def create_node_info(json):
    return NodeInfo(json['cpu'], json['ram'])
