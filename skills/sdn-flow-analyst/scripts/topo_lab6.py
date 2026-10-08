#!/usr/bin/env python3
"""
Mininet Topology for Lab 6:
- Two switches: s1, s2 (interconnected)
- Four hosts connected to s1: h1, h2, h3, h4
- Four hosts connected to s2: h5, h6, h7, h8
- OpenFlow 1.3
- Sequential easy-to-read MAC addresses
"""
try:
    from mininet.topo import Topo  # type: ignore
except ImportError:
    class Topo:  # type: ignore
        def addSwitch(self, *args, **kwargs): pass
        def addHost(self, *args, **kwargs): pass
        def addLink(self, *args, **kwargs): pass
class Lab6Topo(Topo):  # type: ignore
    def build(self):
        # Add two switches
        s1 = self.addSwitch('s1', protocols='OpenFlow13')
        s2 = self.addSwitch('s2', protocols='OpenFlow13')
        
        # Interconnect s1 and s2
        self.addLink(s1, s2)
        
        # Connect 4 hosts to s1 (h1 to h4)
        for i in range(1, 5):
            h = self.addHost(
                'h{}'.format(i),
                ip='10.0.0.{}/24'.format(i),
                mac='00:00:00:00:00:0{}'.format(i)
            )
            self.addLink(h, s1)
            
        # Connect 4 hosts to s2 (h5 to h8)
        for i in range(5, 9):
            h = self.addHost(
                'h{}'.format(i),
                ip='10.0.0.{}/24'.format(i),
                mac='00:00:00:00:00:0{}'.format(i)
            )
            self.addLink(h, s2)

topos = {'lab6topo': Lab6Topo}
