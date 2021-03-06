#!/usr/bin/env python

import rospy, rostest, rosbag
import sys, os, time
import unittest

from robonomics_liability.player import Player
from tempfile import TemporaryDirectory
from urllib.parse import urlparse
from std_msgs.msg import *

PKG = 'robonomics_liability'
NAME = 'test_player'


class TestPlayer(unittest.TestCase):

    def __init__(self, *args):
        rospy.init_node(NAME)
        super(TestPlayer, self).__init__(*args)
        self.subscribers_msg_counters = {}

    def decrement_subscriber_msg_counter(self, topic):
        dcmnt = self.subscribers_msg_counters[topic] - 1
        rospy.loginfo("Decrement topic %s counter from value %s to %s", topic, self.subscribers_msg_counters[topic], dcmnt)
        self.subscribers_msg_counters[topic] = dcmnt

    def test_player(self):
        with TemporaryDirectory() as tmpdir:
            os.chdir(tmpdir)

            test_bag = rosbag.Bag('output.bag', 'w')
            email_data = String(data='test@mail')
            droneid_data = String(data='test_drone_000')
            test_bag.write('/agent/objective/droneid', droneid_data, rospy.Time().now())
            test_bag.write('/agent/objective/email', email_data, rospy.Time().now())
            test_bag.close()

            bag = rosbag.Bag('output.bag', 'r')

            subscribers = {}

            bag_topics = bag.get_type_and_topic_info()
            for topic, topic_info in bag_topics[1].items():
                self.subscribers_msg_counters[topic] = topic_info[1]
                rospy.loginfo("rosbag contains %s messages of type %s in topic %s", topic_info[1], topic_info[0], topic)

            def createSubscriberForTopic(topic, msg):
                rospy.loginfo('Create subscriber %s class %s', topic, msg.__class__)
                subscribers[topic] = rospy.Subscriber(topic,
                                                      msg.__class__,
                                                      lambda m: self.decrement_subscriber_msg_counter(topic))

            for topic, msg, _ in bag.read_messages():
                if topic not in subscribers:
                    createSubscriberForTopic(topic, msg)

            time.sleep(3)
            rospy.loginfo("Start player")
            test_player_start_timestamp = rospy.Time.from_sec(0)
            player = Player(bag, "0x0000000000000000000000000000000000000000")
            player.start(test_player_start_timestamp)
            time.sleep(3)

            for topic in self.subscribers_msg_counters:
                self.assertEqual(0, self.subscribers_msg_counters[topic],
                                 'Expected {0} more messages in topic {1}'.format(self.subscribers_msg_counters[topic], topic))
            rospy.loginfo("All messages from bag published")


if __name__ == '__main__':
    rostest.rosrun(PKG, NAME, TestPlayer, sys.argv)