#
# This file is protected by Copyright. Please refer to the COPYRIGHT file distributed with this
# source distribution.
#
# This file is part of REDHAWK Basic Components FileReader.
#
# REDHAWK Basic Components FileReader is free software: you can redistribute it and/or modify it under the terms of
# the GNU Lesser General Public License as published by the Free Software Foundation, either
# version 3 of the License, or (at your option) any later version.
#
# REDHAWK Basic Components FileReader is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY;
# without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR
# PURPOSE.  See the GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License along with this
# program.  If not, see http://www.gnu.org/licenses/.
#

AC_INIT(rh.FileReader, 5.0.1)
AM_INIT_AUTOMAKE([nostdinc foreign])
AC_CONFIG_MACRO_DIR([m4])

AC_PROG_CC
AC_PROG_CXX
AC_PROG_INSTALL

AC_CORBA_ORB
OSSIE_CHECK_OSSIE
OSSIE_SDRROOT_AS_PREFIX

m4_ifdef([AM_SILENT_RULES], [AM_SILENT_RULES([yes])])

AX_LIB_EXPAT([1.95.8])
if test x"$HAVE_EXPAT" = xno ; then
  AC_MSG_ERROR([The Expat XML parser library and header files are required])
fi

# Dependencies
PKG_CHECK_MODULES([PROJECTDEPS], [ossie >= 2.0 omniORB4 >= 4.1.0])
PKG_CHECK_MODULES([INTERFACEDEPS], [bulkio >= 2.0])
RH_SOFTPKG_CXX([/deps/rh/RedhawkDevUtils/RedhawkDevUtils.spd.xml],[cpp],[5.0])
RH_SOFTPKG_CXX([/deps/rh/blueFileLib/blueFileLib.spd.xml],[cpp],[2.1])
OSSIE_ENABLE_LOG4CXX
AX_BOOST_BASE([1.41])
AX_BOOST_SYSTEM
AX_BOOST_THREAD
AX_BOOST_REGEX

AC_CONFIG_FILES([Makefile])
AC_OUTPUT

