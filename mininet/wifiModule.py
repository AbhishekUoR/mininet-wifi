"""
author: Ramon Fontes (ramonrf@dca.fee.unicamp.br)
"""

import glob
import os
import re
import subprocess
import time
from mininet.log import debug, info
from mininet.link import TCLinkWireless
from mininet.wifiMobility import mobility
from subprocess import ( check_output as co,
                         CalledProcessError )

class module(object):
    """ Start and Stop mac80211_hwsim module """

    wlan_list = []

    @classmethod
    def killprocs(self, pattern):
        "Reliably terminate processes matching a pattern (including args)"
        os.system('pkill -9 -f %s' % pattern)
        # Make sure they are gone
        while True:
            try:
                pids = co([ 'pgrep', '-f', pattern ])
            except CalledProcessError:
                pids = ''
            if pids:
                os.system('pkill -9 -f %s' % pattern)
                time.sleep(.5)
            else:
                break

    @classmethod
    def loadModule(self, wifiRadios, alternativeModule=''):
        """ Start wireless Module """
        if alternativeModule == '':
            os.system('modprobe mac80211_hwsim radios=%s' % wifiRadios)
            debug('Loading %s virtual interfaces\n' % wifiRadios)
        else:
            os.system('insmod %s radios=%s' % (alternativeModule, wifiRadios))
            debug('Loading %s virtual interfaces\n' % wifiRadios)

    @classmethod
    def stop(self):
        """ Stop wireless Module """
        if glob.glob("*.apconf"):
            os.system('rm *.apconf')

        try:
            subprocess.check_output("lsmod | grep mac80211_hwsim",
                                                          shell=True)
            os.system('rmmod mac80211_hwsim')
        except:
            pass
        if mobility.apList != []:
            self.killprocs('hostapd')
            
        try:
            h = subprocess.check_output("ps -aux | grep -ic \'wpa_supplicant -B -Dnl80211\'",
                                                          shell=True)
            if h >= 2:
                os.system('pkill -f \'wpa_supplicant -B -Dnl80211\'')
        except:
            pass

    @classmethod
    def start(self, nodes, wifiRadios, alternativeModule=''):
        """Starting environment"""
        self.killprocs('hostapd')
        try:
            (subprocess.check_output("lsmod | grep mac80211_hwsim",
                                                          shell=True))
            os.system('rmmod mac80211_hwsim')
        except:
            pass

        physicalWlan_list = self.getPhysicalWlan()  # Get Phisical Wlan(s)
        self.loadModule(wifiRadios, alternativeModule)  # Initatilize WiFi Module
        phy_list = self.getPhy()  # Get Phy Interfaces
        module.assignIface(nodes, physicalWlan_list, phy_list)

    @classmethod
    def getPhysicalWlan(self):
        self.wlans = []
        self.wlans = (subprocess.check_output("iwconfig 2>&1 | grep IEEE | awk '{print $1}'",
                                                      shell=True)).split('\n')
        self.wlans.pop()
        return self.wlans

    @classmethod
    def getPhy(self):
        """ Get phy """
        phy = subprocess.check_output("find /sys/kernel/debug/ieee80211 -name hwsim | cut -d/ -f 6 | sort",
                                                             shell=True).split("\n")
        phy.pop()
        phy.sort(key=len, reverse=False)
        return phy
    
    @classmethod
    def getMacAddress(self, sta, wlan):
        """ get Mac Address of any Interface """
        _macMatchRegex = re.compile(r'..:..:..:..:..:..')
        debug('ifconfig %s' % sta.params['wlan'][wlan])
        ifconfig = str(sta.pexec('ifconfig %s' % sta.params['wlan'][wlan]))
        mac = _macMatchRegex.findall(ifconfig)
        return mac[0]
    
    @classmethod
    def setMacAddress(self, sta, wlan):
        sta.pexec('ip link set %s down' % sta.params['wlan'][wlan])
        debug('ip link set %s address %s\n' % (sta.params['wlan'][wlan], sta.params['mac'][wlan]))
        sta.pexec('ip link set %s address %s' % (sta.params['wlan'][wlan], sta.params['mac'][wlan]))
        sta.pexec('ip link set %s up' % sta.params['wlan'][wlan])

    @classmethod
    def assignIface(self, wifiNodes, physicalWlan_list, phy_list):
        try:
            i = 0
            self.wlan_list = self.getWlanIface(physicalWlan_list)
            for sta in wifiNodes:
                if sta.type == 'station' or sta.type == 'vehicle':
                    for wlan in range(0, len(sta.params['wlan'])):
                        os.system('iw phy %s set netns %s' % (phy_list[i], sta.pid))
                        if 'car' in sta.name and sta.type == 'station':
                            sta.cmd('ip link set %s name %s up' % (self.wlan_list[i], sta.params['wlan'][wlan]))
                            sta.cmd('iw dev %s-wlan%s interface add %s-mp%s type mp' % (sta, wlan, sta, wlan))
                            sta.cmd('ifconfig %s-mp%s up' % (sta, wlan))
                            sta.cmd('iw dev %s-mp%s mesh join %s' % (sta, wlan, 'ssid'))
                            sta.func[wlan] = 'mesh'
                        else:
                            sta.cmd('ip link set %s name %s up' % (self.wlan_list[i], sta.params['wlan'][wlan]))
                            cls = TCLinkWireless
                            cls(sta)
                            if sta.params['txpower'][wlan] != 20:
                                sta.cmd('iwconfig %s txpower %s' % (sta.params['wlan'][wlan], sta.params['txpower'][wlan]))
                        if sta.params['mac'][wlan] == '':
                            sta.params['mac'][wlan] = self.getMacAddress(sta, wlan)
                        else:
                            self.setMacAddress(sta, wlan)
                        i+=1
                else:
                    i+=1
        except:
            info( "Something is wrong. Please, run sudo mn -c before running your code.\n" )
            exit(1)

    @classmethod
    def getWlanIface(self, physicalWlan):
        wlan_list = []
        iface_list = subprocess.check_output("iwconfig 2>&1 | grep IEEE | awk '{print $1}'",
                                            shell=True).split('\n')
        for iface in iface_list:
            if iface not in physicalWlan and iface != "":
                wlan_list.append(iface)
        wlan_list = sorted(wlan_list)
        wlan_list.sort(key=len, reverse=False)
        return wlan_list
