import socket
import argparse


def conn_scan(tgt_host, tgt_port):
    skt = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        skt.connect((tgt_host, tgt_port))
        skt.send("Header message".encode())
        results = skt.recv(200)
        print("[+]{}/tcp port opened".format(tgt_port))
        print("[+]", results.decode())
        skt.close()
    except Exception as e:
        print(e)
        print("[-]{}/tcp port closed".format(tgt_port))

def port_scan(tgt_host, tgt_ports):
    try:
        tgt_ip = socket.gethostbyname(tgt_host)