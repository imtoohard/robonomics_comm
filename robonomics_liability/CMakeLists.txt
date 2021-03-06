cmake_minimum_required(VERSION 2.8.3)
project(robonomics_liability)

find_package(catkin REQUIRED
    COMPONENTS
        rospy
        ipfs_common
        ethereum_common
        robonomics_msgs
        message_generation
)

catkin_python_setup()

add_message_files(
    FILES
        Liability.msg
        LiabilityExecutionTimestamp.msg
)

## Generate services in the 'srv' folder
add_service_files(
    FILES
        FinishLiability.srv
        StartLiability.srv
        PersistenceContainsLiability.srv
        PersistenceLiabilityTimestamp.srv
        CreateRosbagPlayer.srv
        StartRosbagPlayer.srv
        StopRosbagPlayer.srv
        ReadLiability.srv
)

generate_messages(
    DEPENDENCIES
        ipfs_common
        ethereum_common
        robonomics_msgs
)

catkin_package()

catkin_install_python(
    PROGRAMS
        scripts/listener_node
        scripts/executor_node
        scripts/persistence_node
        scripts/player_service_node
    DESTINATION
        ${CATKIN_PACKAGE_BIN_DESTINATION}
)

install(
    FILES
        launch/liability.launch
    DESTINATION
        ${CATKIN_PACKAGE_SHARE_DESTINATION}/launch
)

install(
    FILES
        abi/liability.json
        abi/factory.json
    DESTINATION
        ${CATKIN_PACKAGE_SHARE_DESTINATION}/abi
)

install(
    FILES
        tests/liability.test
    DESTINATION
        ${CATKIN_PACKAGE_SHARE_DESTINATION}/tests
)

catkin_install_python(
    PROGRAMS
        tests/test_executor.py
        tests/test_player.py
        tests/test_recorder.py
        tests/test_infochan.py
        tests/test_messageValidator.py
        tests/test_signer.py
        tests/testMessages.py
    DESTINATION
        ${CATKIN_PACKAGE_BIN_DESTINATION}
)
