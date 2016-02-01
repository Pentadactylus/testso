#   Copyright 2015 Zuercher Hochschule fuer Angewandte Wissenschaften
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.

import os
import uuid # for the stack name
from sdk.mcn import util
from sm.so import service_orchestrator
from sm.so.service_orchestrator import LOG
# from neutronclient import client
import ConfigParser

class SOE(service_orchestrator.Execution):
    def __init__(self, token, tenant):
        LOG.info( "initializing stack")

        super(SOE, self).__init__(token, tenant)
        self.token = token
        self.tenant = tenant

        self.hadoop_master = None
        self.deployer = util.get_deployer(self.token,
                                          url_type='public',
                                          tenant_name=self.tenant)

        LOG.info("token = "+self.token)
        LOG.info("tenant = "+self.tenant)

        # the instance variables have to be initialised - for more details, see
        # defaultSettings.cfg
        self.clusterName = None
        self.masterImage = None
        self.slaveImage = None
        self.masterFlavor = None
        self.slaveFlavor = None
        self.slaveOnMaster = None
        self.SSHPublicKeyName = None
        self.SSHMasterPublicKey = None
        self.withFloatingIP = None
        self.master_name = None
        self.slave_name = None
        self.subnet_cidr = None
        self.subnet_gw_ip = None
        self.subnet_allocation_pool_start = None
        self.subnet_allocation_pool_end = None
        self.subnet_dns_servers = None
        self.image_id = None
        self.floatingIpId = None
        self.slaveCount = None

        self.masterBash = None
        self.transferMethod = None
        self.diskId = None

        self.username = None
        self.usergroup = None
        self.homedir = None

        self.saveToLocalPath = None
        self.noDeployment = None

        self.createVolumeForAttachment = None

    def design(self):
        LOG.info("designing stack")

        """
        Do initial design steps here.
        """
        LOG.info('Entered design() - nothing to do here')
        # self.resolver.design()

    def deploy(self, attributes=None):
        # this function will return the first of following values in the order
        # of occurrence:
        #   - given by the user during instantiation
        #   - set as a default value in the config file
        #   - an empty string
        def getAttr(attrName):
            if(attrName in attributes):
                return attributes[attrName]
            else:
                try:
                    return config.get('cluster',attrName)
                except:
                    return ""

        # the rootFolder is needed in order to load the config files
        self.rootFolder = getAttr('icclab.haas.rootfolder')
        if self.rootFolder=="":
            # if no rootFolder has been provided, take the path it's located
            # within the Docker image
            self.rootFolder = "data/"

        # setup parser for config file
        config = ConfigParser.RawConfigParser()
        config.read(os.path.join(self.rootFolder,'defaultSettings.cfg'))

        LOG.info("deploying stack...")

        # the needed variables for the Heat Orchestration Template will be set
        # on the following lines; the function getAttr() is returning the
        # appropriate value. As an empty value cannot be used for int/float
        # conversion, they have to be set within a try-except block.
        # masterCount = 1
        # try:
        #     masterCount = int(getAttr('icclab.haas.master.number'))
        # except:
        #     pass
        self.slaveCount = 1
        try:
            self.slaveCount = int(getAttr('icclab.haas.slave.number'))
        except:
            pass
        self.clusterName = getAttr('icclab.haas.cluster.name')
        self.masterImage = getAttr('icclab.haas.master.image')
        self.slaveImage = getAttr('icclab.haas.slave.image')
        self.masterFlavor = getAttr('icclab.haas.master.flavor')
        self.slaveFlavor = getAttr('icclab.haas.slave.flavor')
        self.slaveOnMaster = getAttr('icclab.haas.master.slaveonmaster').lower() in ['true', '1']
        self.SSHPublicKeyName = getAttr('icclab.haas.master.sshkeyname')
        self.SSHMasterPublicKey = getAttr('icclab.haas.master.publickey')
        self.withFloatingIP = getAttr('icclab.haas.master.withfloatingip').lower() in ['true','1']
        self.master_name = getAttr('icclab.haas.master.name')
        self.slave_name = getAttr('icclab.haas.slave.name')
        self.subnet_cidr = getAttr('icclab.haas.network.subnet.cidr')
        self.subnet_gw_ip = getAttr('icclab.haas.network.gw.ip')
        self.subnet_allocation_pool_start = getAttr('icclab.haas.network.subnet.allocpool.start')
        self.subnet_allocation_pool_end = getAttr('icclab.haas.network.subnet.allocpool.end')
        self.subnet_dns_servers = getAttr('icclab.haas.network.dnsservers')
        self.image_id = getAttr('icclab.haas.master.imageid')
        self.floatingIpId = getAttr('icclab.haas.master.attachfloatingipwithid')
        self.transferMethod = getAttr('icclab.haas.master.transfermethod')

        self.username = getAttr('icclab.haas.cluster.username')
        self.usergroup = getAttr('icclab.haas.cluster.usergroup')
        self.homedir = getAttr('icclab.haas.cluster.homedir')

        self.noDeployment = getAttr('icclab.haas.debug.donotdeploy').lower() in ['true','1']
        self.saveToLocalPath = getAttr('icclab.haas.debug.savetemplatetolocalpath')

        self.createVolumeForAttachment = getAttr('icclab.haas.master.createvolumeforattachment').lower() in ['true','1']

        self.diskId = 'virtio-'+self.image_id[0:20]

        masterSSHKeyEntry = ''

        def getFileContent(fileName):
            f = open(os.path.join(self.rootFolder, fileName))
            retVal = f.read()
            f.close()
            return retVal

        # read all the necessary files for creating the Heat template
        clusterTemplate = getFileContent("cluster.yaml");
        slaveTemplate = getFileContent("slave.yaml")
        self.masterBash = getFileContent("master_bash.sh")
        master_id_rsa = getFileContent("master.id_rsa").replace("\n","\\n")
        master_id_rsa_pub = getFileContent("master.id_rsa.pub").replace("\n","")
        yarn_site_xml = getFileContent("yarn-site.xml")
        core_site_xml = getFileContent("core-site.xml")
        mapred_site_xml = getFileContent("mapred-site.xml")
        hdfs_site_xml = getFileContent("hdfs-site.xml")
        hadoop_env_sh = getFileContent("hadoop-env.sh")

        slaves = ""
        hostFileContent = ""
        forLoopSlaves = ""
        paramsSlave = ""
        slavesFile = ""
        hostsListFile = ""


        slaveTemplate = slaveTemplate.replace("$master.id_rsa.pub$",master_id_rsa_pub)
        for i in xrange(1,self.slaveCount+1):
            slaves += slaveTemplate.replace("$slavenumber$",str(i))
            hostFileContent += "$slave"+str(i)+"address$\t"+self.slave_name+str(i)+"\n"
            forLoopSlaves += " $slave"+str(i)+"address$"
            paramsSlave += "            $slave"+str(i)+"address$: { get_attr: [hadoop_slave_"+str(i)+", first_address] }\n"
            slavesFile += self.slave_name+str(i)+"\n"
            hostsListFile += "$slave"+str(i)+"address$\n"

        # In the following section, the master's public SSH key will be setup.
        # This is done the following way: if no key name was provided for an
        # existing public SSH key, the same key will be used as was used for
        # the slaves as well. If a key name was provided but no public SSH key,
        # it's assumed that an existing public key is already registered in
        # keystone which should be used. If a key name and a public SSH key are
        # provided, a new public key entry will be created in keystone with the
        # give public key and the given name.
        masterSSHKeyResource = ""
        insertMasterPublicKey = ""
        if self.SSHPublicKeyName=="":
            masterSSHKeyEntry = "{ get_resource: sshpublickey }"
        else:
            insertMasterPublicKey = "su "+self.username+" -c \"cat "+self.homedir+"/.ssh/id_rsa.pub >> "+self.homedir+"/.ssh/authorized_keys\"\n"
            if self.SSHMasterPublicKey=="":
                masterSSHKeyEntry = self.SSHPublicKeyName
            else:
                masterSSHKeyResource = "  users_public_key:\n" \
                                       "    type: OS::Nova::KeyPair\n" \
                                       "    properties:\n" \
                                       "      name: " + self.SSHPublicKeyName + "\n" \
                                       "      public_key: " + self.SSHMasterPublicKey + "\n\n"
                masterSSHKeyEntry = "{ get_resource: users_public_key }"

        # if master has to act as a slave as well, set variable accordingly
        masterasslave = ""
        if self.slaveOnMaster==True:
            masterasslave = self.master_name+"\n"

        # setup bash script for master (write replace{r,e}s into dictionary and
        # replace them one by one
        replaceDict = { "$master.id_rsa$": master_id_rsa,
                        "$master.id_rsa.pub$": master_id_rsa_pub,
                        "$yarn-site.xml$": yarn_site_xml,
                        "$core-site.xml$": core_site_xml,
                        "$mapred-site.xml$": mapred_site_xml,
                        "$hdfs-site.xml$": hdfs_site_xml,
                        "$hadoop-env.sh$": hadoop_env_sh,
                        "$masternodeasslave$": masterasslave,
                        "$slavesfile$": slavesFile,
                        "$hostsfilecontent$": hostFileContent,
                        "$forloopslaves$": forLoopSlaves,
                        "$for_loop_slaves$": hostsListFile,
                        "$insert_master_pub_key$": insertMasterPublicKey,
                        "$transfer_method$": self.transferMethod,
                        "$disk_id$": self.diskId,
                        "$username$": self.username,
                        "$usergroup$": self.usergroup,
                        "$homedir$": self.homedir
                        }
        for key, value in replaceDict.iteritems():
            self.masterBash = self.masterBash.replace(key, value)

        # add some spaces in front of each line because the bash script has to
        # be indented within the Heat template
        masterBashLines = self.masterBash.splitlines(True)
        self.masterbash = ""
        for line in masterBashLines:
            self.masterbash += ' '*14+line

        # does the user want to have a floating IP created?
        floatingIpResource = ""
        floatingIpAssoc = ""
        externalIpOutput = ""

        # create volume attachment part
        if( self.createVolumeForAttachment ):
            self.createVolumeForAttachment = getFileContent('volumeAttachmentWithCreatedVolume.yaml')
        else:
            self.createVolumeForAttachment = getFileContent('volumeAttachmentWithoutCreatedVolume.yaml')

        # if a floating IP is to be setup for the master, the variables have to be set accordingly
        if True == self.withFloatingIP:
            ipid = self.floatingIpId
            floatingIpAssoc = "  floating_ip_assoc:\n" \
                              "    type: OS::Neutron::FloatingIPAssociation\n" \
                              "    properties:\n" \
                              "      floatingip_id: "
            if self.floatingIpId=="":
                floatingIpResource = "  hadoop_ip:\n" \
                                     "    type: OS::Neutron::FloatingIP\n" \
                                     "    properties:\n" \
                                     "      floating_network: \"external-net\"\n\n"
                floatingIpAssoc += "{ get_resource: hadoop_ip }"
                externalIpOutput = "  external_ip:\n" \
                                   "    description: The IP address of the deployed master node\n" \
                                   "    value: { get_attr: [ hadoop_ip, floating_ip_address ] }\n\n" \
                                   "" \
                                   "  external_ip_id:\n" \
                                   "    description: The IP address' ID of the deployed master node\n" \
                                   "        value: { get_attr: [ hadoop_ip, floating_ip_id ] }\n\n"
            else:
                floatingIpAssoc = floatingIpAssoc+self.floatingIpId
            floatingIpAssoc += "\n      port_id: { get_resource: hadoop_port }\n\n"

        self.createVolumeForAttachment = self.createVolumeForAttachment.replace("$image_id$", self.image_id)

        # the cluster's heat template will have to be configured
        replaceDict = {"$master_bash.sh$": self.masterbash,
                       "$paramsslave$": paramsSlave,
                       "$slaves$": slaves,
                       "$master_image$": self.masterImage,
                       "$slave_image$": self.slaveImage,
                       "$masternode$": self.master_name,
                       "$slavenode$": self.slave_name,
                       "$master_flavor$": self.masterFlavor,
                       "$slave_flavor$": self.slaveFlavor,
                       "$master_ssh_key_entry$": masterSSHKeyEntry,
                       "$users_ssh_public_key$": masterSSHKeyResource,
                       "$floating_ip_resource$": floatingIpResource,
                       "$floating_ip_assoc$": floatingIpAssoc,
                       "$external_ip_output$": externalIpOutput,
                       "$subnet_cidr$": self.subnet_cidr,
                       "$subnet_gw_ip$": self.subnet_gw_ip,
                       "$subnet_allocation_pool_start$":
                           self.subnet_allocation_pool_start,
                       "$subnet_allocation_pool_end$":
                           self.subnet_allocation_pool_end,
                       "$subnet_dns_servers$": self.subnet_dns_servers,
                       "$volume_attachment$": self.createVolumeForAttachment
                    }

        for key, value in replaceDict.iteritems():
            clusterTemplate = clusterTemplate.replace(key, value)

        # for debugging purposes, the template can be saved locally
        if self.saveToLocalPath is not "":
            try:
                f = open( self.saveToLocalPath,"w")
                f.write(clusterTemplate)
                f.close()
            except:
                LOG.info("Couldn't write to location "+self.saveToLocalPath)

        # debug output should be implemented as a parameter
        #   LOG.debug(clusterTemplate)
        self.deployTemplate = clusterTemplate

        # deploy the created template
        if self.hadoop_master is None and not self.noDeployment:


            self.hadoop_master = self.deployer.deploy(self.deployTemplate,
                                                      self.token,
                                                      name=self.clusterName+"_"+str(uuid.uuid1()))


            LOG.info('Hadoop stack ID: ' + self.hadoop_master)

    def provision(self, attributes=None):
        LOG.info( "provisioning stack" );

        """
        provision the SICs on burns and ubern
        """

        LOG.info('Calling provision...')
        LOG.info('nothing to be done to be honest...')
        LOG.debug('Executing resource provisioning logic')
        # once logic executes, deploy phase is done

    def dispose(self):
        LOG.info( "disposal of stack" );

        """
        Dispose SICs on burns and ubern
        """
        LOG.info('Calling dispose')
        # self.resolver.dispose()

        if self.hadoop_master is not None:
            ###################################################################
            # IMPORTANT NOTE: the floating IP has to be disassociated before  #
            # the stack is deleted! Else, disposal will fail. Until now,      #
            # neutronclient hasn't worked doing this which is why it has to   #
            # be done either within OpenStack Horizon or from the terminal!   #
            ###################################################################

            # # check first whether there is a floating ip associated
            # ep = self.deployer.endpoint
            # ep = ep[0:ep.find(":",6)]+":5000/v2.0"
            # neutron = client.Client('2.0', endpoint_url=ep, token=self.token)
            # neutron.format = 'json'
            #
            # # floating IP has to be disassociated before deleting the stack, see
            # # https://ask.openstack.org/en/question/25866/neutron-error/
            # neutron.update_floatingip(self.floatingIpId,
            #                              {'floatingip': {'port_id': None}})

            LOG.debug('Deleting stack: ' + self.hadoop_master)
            self.deployer.dispose(self.hadoop_master, self.token)
            self.hadoop_master = None

    def state(self):
        LOG.info( "getting status of stack")

        """
        Report on state for both stacks in burns and ubern
        """
        if self.hadoop_master is not None:
            tmp = self.deployer.details(self.hadoop_master, self.token)
            if 'output' not in tmp:
                return tmp['state'], self.hadoop_master, dict()
            return tmp['state'], self.hadoop_master, tmp['output']
        else:
            return 'Unknown', 'N/A', {}

    def update(self, old, new, extras):
        LOG.info( "updating stack")

        # TODO implement your own update logic - this could be a heat template
        # update call
        LOG.info('Calling update - nothing to do!')

    def notify(self, entity, attributes, extras):
        LOG.info( "notifying stack")

        super(SOE, self).notify(entity, attributes, extras)
        # TODO here you can add logic to handle a notification event sent by the CC
        # XXX this is optional


class SOD(service_orchestrator.Decision):
    """
    Sample Decision part of SO.
    """

    def __init__(self, so_e, token, tenant):
        super(SOD, self).__init__(so_e, token, tenant)
        self.so_e = so_e
        self.token = token
        self.tenant = tenant

    def run(self):
        """
        Decision part implementation goes here.
        """
        pass

    def stop(self):
        pass


class ServiceOrchestrator(object):
    """
    Sample SO.
    """

    def __init__(self, token, tenant):
        self.so_e = SOE(token=token, tenant=tenant)
        self.so_d = SOD(so_e=self.so_e, tenant=tenant, token=token)
