add_executable(helmetd-test-sender src/main.cpp)
target_link_libraries(helmetd-test-sender PRIVATE PkgConfig::GSTREAMER)
target_compile_options(helmetd-test-sender PRIVATE -Wall -Wextra -Wpedantic)
set_target_properties(helmetd-test-sender PROPERTIES
  RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin")

if(BUILD_TESTING)
  find_package(Python3 REQUIRED COMPONENTS Interpreter)
  find_program(GST_LAUNCH gst-launch-1.0 REQUIRED)
  add_test(NAME hud-media-loopback
    COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/tests/loopback.py"
      --sender "$<TARGET_FILE:helmetd-test-sender>" --gst-launch "${GST_LAUNCH}")
  set_tests_properties(hud-media-loopback PROPERTIES TIMEOUT 55)
endif()
