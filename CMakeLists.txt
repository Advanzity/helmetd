cmake_minimum_required(VERSION 3.24)
project(helmetd VERSION 0.1.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
include(CTest)

find_package(PkgConfig REQUIRED)
pkg_check_modules(GSTREAMER REQUIRED IMPORTED_TARGET gstreamer-1.0>=1.22)

if(APPLE)
  add_subdirectory(apps/hud)
else()
  message(STATUS "The current test sender requires macOS VideoToolbox. Pi targets are pending.")
endif()
