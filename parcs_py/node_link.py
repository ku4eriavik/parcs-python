from .node_info import create_node_info


class NodeLink:
    id = 0

    def __init__(self, ip, port,  info=None):
        self.id = NodeLink.id
        self.ip = ip
        self.port = port
        self.info = info
        self.enabled = True
        NodeLink.id += 1

    def serialize(self):
        return {
            'id': self.id, 'ip': self.ip, 'port': self.port, 'info': self.info.serialize(),
            'enabled':self.enabled
        }

    def __str__(self):
        return "%s:%d)" % (self.ip, self.port)


def create_node_link(json):
    return NodeLink(json['ip'], json['port'],  create_node_info(json['info']))
