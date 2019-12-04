# -*- coding: utf-8 -*-
#
# Robonomics liability execution node.
#

from robonomics_liability.msg import Liability
from robonomics_liability.srv import FinishLiability, FinishLiabilityResponse, \
    StartLiability, StartLiabilityResponse, PersistenceLiabilityTimestamp, \
    ReadLiability
from robonomics_msgs.msg import Result
from threading import Thread
from .LiabilityExecutionThread import LiabilityExecutionThread
from queue import Queue
import rospy
import os
from ethereum_common import eth_keyfile_helper


class Executor:
    liability_queue = Queue()
    liability_finish = False

    def __init__(self):
        '''
            Robonomics liability node initialisation.
        '''
        rospy.init_node('robonomics_liability_executor')

        self.recording_topics = list(filter(None, [x.strip() for x in rospy.get_param('~recording_topics').split(",")]))
        self.master_check_interval = rospy.get_param('~master_check_interval')

        __keyfile = rospy.get_param('~keyfile')
        __keyfile_password_file = rospy.get_param('~keyfile_password_file')
        __keyfile_helper = eth_keyfile_helper.KeyfileHelper(__keyfile, keyfile_password_file=__keyfile_password_file)
        self.__account = __keyfile_helper.get_local_account_from_keyfile()

        self.liability_execution_threads = {}

        # persistence publishers
        self.persistence_add = rospy.Publisher('persistence/add', Liability, queue_size=10)
        self.persistence_del = rospy.Publisher('persistence/del', Liability, queue_size=10)
        # persistence services
        self.persistence_get_liability_timestamp = rospy.ServiceProxy('persistence/get_liability_timestamp', PersistenceLiabilityTimestamp)

        self.read_libility_srv = rospy.ServiceProxy('read', ReadLiability)

        self.executions_work_directory = os.path.join(os.getcwd(), 'liabilities_executions')

        def incoming_liability(msg):
            if msg.promisor.address != self.__account.address:
                rospy.logwarn('Liability %s is not for me, SKIP.', msg.address)
            else:
                rospy.loginfo('Append %s to liability queue.', msg.address)
                self.persistence_add.publish(msg)
                self.liability_queue.put(msg)
        rospy.Subscriber('incoming', Liability, incoming_liability)

        def finish_liability(msg):
            liability_thread = self.liability_execution_threads.pop(msg.address.address)

            liability_msg = liability_thread.getLiabilityMsg()

            result_ipfs_address = liability_thread.finish(msg.success)
            result = Result()
            result.liability = liability_msg.address
            result.result = result_ipfs_address
            result.success = msg.success

            self.persistence_del.publish(liability_msg)

            self.complete.publish(liability_msg)
            self.result_topic.publish(result)
            rospy.loginfo('Liability %s finished with %s', liability_msg.address.address, result.result)
            return FinishLiabilityResponse()
        rospy.Service('finish', FinishLiability, finish_liability)

        def start_liability(msg):
            if msg.address.address not in self.liability_execution_threads:
                rospy.wait_for_service(self.read_libility_srv.resolved_name)

                read_liability_response = self.read_libility_srv(msg.address)
                if not read_liability_response.read:
                    return StartLiabilityResponse(False,
                                                  "Could not find {0} in ready liabilities or read them from chain for starting".format(msg.address.address))
                try:
                    self.persistence_add.publish(read_liability_response.liability)
                    self._createLiabilityExceutionThread(read_liability_response.liability)
                except Exception as e:
                    rospy.logerr("Failed to prepare liability {0} to execution with e: {1}".format(msg.address.address, e))
                    return StartLiabilityResponse(False, "Failed to prepare liability {0} to execution with e: {1}".format(msg.address.address, e))

            liability_thread = self.liability_execution_threads[msg.address.address]

            try:
                liability_thread.start()
                rospy.loginfo('Liability %s started', liability_thread.getLiabilityMsg().address.address)
            except Exception as e:
                rospy.logerr("Can't start liability %s with %s", msg.address.address, e)
                return StartLiabilityResponse(False, "Can't start liability {0} with exception: {1}".format(msg.address.address, e))

            return StartLiabilityResponse(True, "Liability {0} started".format(liability_thread.getLiabilityMsg().address.address))
        rospy.Service('start', StartLiability, start_liability)

        def restart_liability(msg):
            try:
                liability_thread = self.liability_execution_threads.pop(msg.address.address)
            except KeyError as e:
                rospy.logerr("Could not find liability %s for restarting", msg.address.address)
                return StartLiabilityResponse(False, "Could not find liability {0} for restarting".format(msg.address.address))

            liability = liability_thread.getLiabilityMsg()
            try:
                liability_thread.interrupt(delete_result=True)
                rospy.loginfo('Liability %s interrupted', liability.address.address)
            except Exception as e:
                rospy.logerr("Can't interrupt liability %s with %s", msg.address.address, e)
                return StartLiabilityResponse(False,
                                              "Can't interrupt liability {0} with exception: {1}".format(msg.address.address, e))
            try:
                self._createLiabilityExceutionThread(liability)
            except Exception as e:
                return StartLiabilityResponse(False, "Can't initialize liability {0} execution thread with exception: {1}".format(msg.address.address, e))
            return start_liability(msg)
        rospy.Service('restart', StartLiability, restart_liability)

        def resume_liability(msg):
            try:
                liability_thread = self.liability_execution_threads[msg.address.address]
            except KeyError as e:
                rospy.logerr("Could not find liability %s for resuming", msg.address.address)
                return StartLiabilityResponse(False, "Could not find liability {0} for resuming".format(msg.address.address))
            try:
                rospy.wait_for_service(self.persistence_get_liability_timestamp.resolved_name)
                timestamp = self.persistence_get_liability_timestamp(liability_thread.getLiabilityMsg().address)
                rospy.logwarn("Getting %s timestamp for liability %s", timestamp.timestamp, msg.address.address)
                liability_thread.start(timestamp.timestamp)
                rospy.loginfo('Liability %s resumed', liability_thread.getLiabilityMsg().address.address)
            except Exception as e:
                rospy.logerr("Can't resume liability %s with %s", msg.address.address, e)
                return StartLiabilityResponse(False, "Can't resume liability {0} with exception: {1}".format(msg.address.address, e))

            return StartLiabilityResponse(True, "Liability {0} resumed".format(liability_thread.getLiabilityMsg().address.address))
        rospy.Service('resume', StartLiability, resume_liability)

        self.complete =     rospy.Publisher('complete', Liability, queue_size=10)
        self.ready  =       rospy.Publisher('ready', Liability, queue_size=10)
        self.result_topic = rospy.Publisher('result', Result, queue_size=10)

    def _createLiabilityExceutionThread(self, liability):
        liability_work_directory = os.path.join(self.executions_work_directory, liability.address.address)
        os.makedirs(liability_work_directory, exist_ok=True)
        rospy.loginfo('Use directory %s for liability %s executor thread',
                      liability_work_directory, liability.address.address)
        thread = LiabilityExecutionThread(liability_work_directory,
                                          self.master_check_interval,
                                          self.recording_topics,
                                          liability=liability)
        self.liability_execution_threads[liability.address.address] = thread

    def _liability_worker(self):
        while not rospy.is_shutdown():
            msg = self.liability_queue.get()
            rospy.loginfo('Prepare to start liability %s', msg.address.address)

            try:
                self._createLiabilityExceutionThread(msg)
                self.ready.publish(msg)
            except Exception as e:
                rospy.logerr("Failed to prepare liability execution thread for %s with exception \"%s\"", msg.address, e)

    def spin(self):
        '''
            Waiting for the new messages.
        '''
        Thread(target=self._liability_worker, daemon=True).start()
        rospy.spin()
