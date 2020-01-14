#!/usr/bin/env python3
import socket
import select
import struct 
import threading
import logging
import argparse

__version__ = 1.0
__author__ = 'Glemison Dutra'

logger = logging.getLogger(__name__)

VERSION = b'\x05'
NOAUTH = b'\x00'
NOTAVAILABLE = b'\xff'
COMMAND_CONNECT = b'\x01'
TYP_IPV4 = b'\x01'
TYP_DOMAIN = b'\x03'

class Connection:
	def __init__(self):
		self.conn = None
		
	def send(self, data):
		self.conn.sendall(data)

	def recv(self, size=8192):
		try:
			data = self.conn.recv(size)
			if not data: return None
			return data
		except:
			return None
	
	def close(self):
		self.conn.close()

class Client(Connection):
	def __init__(self, client, addr):
		super(Client, self).__init__()
		self.conn = client
		self.addr = addr

class Server(Connection):
	def __init__(self, addr):
		super(Server, self).__init__()
		self.addr = addr
		
	def connect(self):
		self.conn = socket.create_connection(self.addr, 5)
		self.conn.settimeout(None)

class Handler(threading.Thread):
	def __init__(self, client):
		super(Handler, self).__init__()
		self.client = client
		self.server = None
	
	def request_client(self):
		data = self.client.recv()
		if (data[0:1] != VERSION or
			data[1:2] != COMMAND_CONNECT or
			data[2:3] != b'\x00'):
			return None
		if data[3:4] == TYP_IPV4:
			hostname = socket.inet_ntoa(data[4:-2])
			port = struct.unpack('>H', data[8:len(data)])[0]
		elif data[3:4] == TYP_DOMAIN:
			size_domain = data[4]
			hostname = data[5: 5 + size_domain - len(data)]
			port_unpack = data[5 + size_domain:len(data)]
			port = struct.unpack('>H', port_unpack)[0]
		else:
			return None
		return hostname, port
	
	def request(self):
		addr = self.request_client()
		if addr:
			self.server = Server(addr)
			try:
				logger.info('Conectando ao servidor %s:%d...' % addr)
				self.server.connect()
				logger.info('Conectado ao servidor %s:%d' % addr)
				self.client.send(
					VERSION + b'\x00' + b'\x00' + TYP_IPV4 + \
					socket.inet_aton(self.server.conn.getsockname()[0]) + \
					struct.pack('>H', self.server.conn.getsockname()[1])
				)
				return True
			except Exception as e:
				self.client.send(
					VERSION + b'\x01' + b'\x00' + TYP_IPV4 + \
					b'\x00' + b'\x00' + b'\x00' + b'\x00' + b'\x00' + b'\x00' + \
					socket.inet_aton(self.server.conn.getsockname()[0]) + \
					struct.pack('>H', self.server.conn.getsockname()[1])
				)
				logger.error('Nao foi possivel conectar ao servidor %s:%d' % addr)
				logger.debug('Error: %r' % e)
				return False
		
	def verify_methods(self):
		data = self.client.recv()
		if data[0:1] == VERSION:
			if len(data[2:]) == data[1]:
				for method in data[2:]:
					if method == ord(NOAUTH):
						return NOAUTH
		return NOTAVAILABLE

	def process_rlist(self, rlist):
		if self.client.conn in rlist:
			data = self.client.recv()
			if not data: return True
			self.server.send(data)

		if self.server.conn in rlist:
			data = self.server.recv()
			if not data: return True
			self.client.send(data)

	def process(self):
		while True:
			rlist, _, _ = select.select([self.client.conn, self.server.conn], [], [], 5)
			if self.process_rlist(rlist): break

	def run(self):
		try:
			logger.info('Cliente conectado %s:%d' % self.client.addr)
			data = self.verify_methods()
			if data == b'\x00':
				self.client.send(b'\x05\x00')
				if self.request():
					self.process()
		except Exception as e:
			logger.debug('Error: %r' % e)
		finally:
			if self.server: self.server.close()
			self.client.close()
			logger.info('Cliente desconectado %s:%d' % self.client.addr)

class Clients:
	def __init__(self):
		self.clients = []
		self.lock = threading.Lock()
	
	def add_client(self, client):
		self.clients.append(client)

	def remove_client(self, client):
		self.clients.remove(client)
	
	def check_active_clients(self):
		for client in self.clients:
			if not client.isAlive():
				self.remove_client(client)

	def clients_connected(self):
		return self.clients
	
class Socks5(Clients):
	def __init__(self, host, port, limit):
		super(Socks5, self).__init__()
		self.host = host
		self.port = port
		self.limit_connections = limit
		self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

	def handler(self, client):
		handler = Handler(client)
		handler.daemon = True
		handler.start()
		self.add_client(handler)

	def verify_number_of_clients(self):
		if len(self.clients_connected()) < self.limit_connections:
			return True
		return False

	def run(self):
		logger.info('Iniciando socks5: %s:%d' % (self.host, self.port))
		try:
			self.socket.bind((self.host, self.port))
			self.socket.listen(0)
			logger.debug('proxy socks5 ativado!')
			while True:
				if self.verify_number_of_clients():
					conn, addr = self.socket.accept()
					client = Client(conn, addr)
					self.handler(client)
				else:
					self.check_active_clients()
		except Exception as e:
			logger.error('%r' % e)
		finally:
			logger.info('Parado proxy socks5...')
			self.socket.close()

def main():
	parser = argparse.ArgumentParser(
		description='socks5.py v%s' % __version__)

	parser.add_argument('--hostname', default='127.0.0.1', help='Default: 127.0.0.1')
	parser.add_argument('--port', default='8888', help='Default: 8888')
	parser.add_argument('--limit-connections', default='250', help='Default: 250. ' \
		'Numero maximo de conexoes simultâneos')
	parser.add_argument('--log-level', default='INFO', help='DEBUG, INFO (default), WARNING, ERROR')
	args = parser.parse_args()

	logging.basicConfig(
		level=getattr(logging, args.log_level),
		format='%(asctime)s - %(levelname)s - %(message)s',
		datefmt='%H:%M:%S'
	)
	try:
		proxy = Socks5(args.hostname, int(args.port), int(args.limit_connections))
		proxy.run()
	except KeyboardInterrupt:
		pass

if __name__ == '__main__':
	main()
