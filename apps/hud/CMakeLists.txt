add_executable(helmetd-test-sender src/main.cpp)
target_link_libraries(helmetd-test-sender PRIVATE PkgConfig::GSTREAMER)
target_compile_options(helmetd-test-sender PRIVATE -Wall -Wextra -Wpedantic)
set_target_properties(helmetd-test-sender PROPERTIES
  RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin")

enable_language(OBJCXX)
pkg_check_modules(GSTREAMER_APP REQUIRED IMPORTED_TARGET
  gstreamer-app-1.0>=1.22 gstreamer-video-1.0>=1.22)
add_executable(helmetd-hud
  src/hud_main.cpp src/hud_options.cpp src/hud_control.cpp src/media.cpp src/metal_renderer.mm src/perception_worker.cpp)
set_target_properties(helmetd-hud PROPERTIES
  OBJCXX_STANDARD 20 OBJCXX_STANDARD_REQUIRED ON OBJCXX_EXTENSIONS OFF
  RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin")
target_compile_options(helmetd-hud PRIVATE -Wall -Wextra -Wpedantic
  "$<$<COMPILE_LANGUAGE:OBJCXX>:-fobjc-arc>")
target_link_libraries(helmetd-hud PRIVATE PkgConfig::GSTREAMER PkgConfig::GSTREAMER_APP
  helmetd-perception
  "-framework MetalKit" "-framework AppKit" "-framework Metal" "-framework QuartzCore" "-framework CoreText")
add_custom_command(TARGET helmetd-hud POST_BUILD
  COMMAND "${CMAKE_COMMAND}" -E make_directory "${CMAKE_BINARY_DIR}/bin/Helmetd.app/Contents/MacOS"
  COMMAND "${CMAKE_COMMAND}" -E copy "$<TARGET_FILE:helmetd-hud>"
    "${CMAKE_BINARY_DIR}/bin/Helmetd.app/Contents/MacOS/helmetd-hud"
  COMMAND "${CMAKE_COMMAND}" -E copy "${CMAKE_CURRENT_SOURCE_DIR}/Info.plist"
    "${CMAKE_BINARY_DIR}/bin/Helmetd.app/Contents/Info.plist")
set_property(TARGET helmetd-hud APPEND PROPERTY LINK_DEPENDS "${CMAKE_CURRENT_SOURCE_DIR}/Info.plist")

if(BUILD_TESTING)
  find_package(Python3 REQUIRED COMPONENTS Interpreter)
  find_program(GST_LAUNCH gst-launch-1.0 REQUIRED)
  add_test(NAME hud-media-loopback
    COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/tests/loopback.py"
      --sender "$<TARGET_FILE:helmetd-test-sender>" --gst-launch "${GST_LAUNCH}")
  set_tests_properties(hud-media-loopback PROPERTIES TIMEOUT 55)

  add_executable(helmetd-hud-state-test tests/state.cpp src/hud_options.cpp)
  target_include_directories(helmetd-hud-state-test PRIVATE src)
  target_link_libraries(helmetd-hud-state-test PRIVATE helmetd-perception)
  target_compile_options(helmetd-hud-state-test PRIVATE -Wall -Wextra -Wpedantic)
  add_test(NAME hud-state COMMAND helmetd-hud-state-test)
  add_executable(helmetd-hud-control-test tests/control.cpp src/hud_control.cpp)
  target_include_directories(helmetd-hud-control-test PRIVATE src)
  target_link_libraries(helmetd-hud-control-test PRIVATE helmetd-perception)
  add_test(NAME hud-control COMMAND helmetd-hud-control-test)
  add_test(NAME hud-voice-control
    COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/tests/voice_control.py"
      --hud "$<TARGET_FILE:helmetd-hud>")
  set_tests_properties(hud-voice-control PROPERTIES TIMEOUT 25 RESOURCE_LOCK helmetd_media)
  add_test(NAME hud-native-render
    COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/tests/native_render.py"
      --hud "$<TARGET_FILE:helmetd-hud>" --gst-launch "${GST_LAUNCH}")
  set_tests_properties(hud-native-render PROPERTIES TIMEOUT 45)
  add_test(NAME hud-native-loopback
    COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/tests/loopback.py"
      --sender "$<TARGET_FILE:helmetd-hud>" --gst-launch "${GST_LAUNCH}" --headless)
  set_tests_properties(hud-native-loopback PROPERTIES TIMEOUT 55)
  add_test(NAME hud-camera-uplink
    COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/tests/camera_uplink.py"
      --hud "$<TARGET_FILE:helmetd-hud>" --gst-launch "${GST_LAUNCH}")
  set_tests_properties(hud-camera-uplink PROPERTIES TIMEOUT 45)
  add_test(NAME hud-camera-failure
    COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/tests/camera_uplink.py"
      --hud "$<TARGET_FILE:helmetd-hud>" --gst-launch "${GST_LAUNCH}" --reject-profile)
  set_tests_properties(hud-camera-failure PROPERTIES TIMEOUT 45)
  add_test(NAME hud-multi-camera
    COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/tests/multi_camera.py"
      --hud "$<TARGET_FILE:helmetd-hud>" --gst-launch "${GST_LAUNCH}")
  set_tests_properties(hud-multi-camera PROPERTIES TIMEOUT 55 RESOURCE_LOCK helmetd_media)
  set_tests_properties(hud-media-loopback hud-native-render hud-native-loopback
    hud-camera-uplink hud-camera-failure PROPERTIES RESOURCE_LOCK helmetd_media)
endif()

add_executable(helmetd-map-renderer ../map-renderer/main.mm)
set_target_properties(helmetd-map-renderer PROPERTIES OBJCXX_STANDARD 20
  RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin")
target_compile_options(helmetd-map-renderer PRIVATE -fobjc-arc)
target_link_libraries(helmetd-map-renderer PRIVATE "-framework MetalKit" "-framework AppKit" "-framework WebKit")

configure_file("${PROJECT_SOURCE_DIR}/docs/design/hud/assets/hud-symbols-v1.png"
  "${CMAKE_BINARY_DIR}/bin/hud-symbols-v1.png" COPYONLY)
target_compile_definitions(helmetd-hud PRIVATE HELMETD_SPRITE_PATH="${CMAKE_BINARY_DIR}/bin/hud-symbols-v1.png")

configure_file("${PROJECT_SOURCE_DIR}/docs/design/hud/assets/notification-white-v1.png"
  "${CMAKE_BINARY_DIR}/bin/notification-white-v1.png" COPYONLY)
target_compile_definitions(helmetd-hud PRIVATE HELMETD_NOTIFICATION_PATH="${CMAKE_BINARY_DIR}/bin/notification-white-v1.png")
