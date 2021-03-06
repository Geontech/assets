###############################################################################
# This file is protected by Copyright. Please refer to the COPYRIGHT file
# distributed with this source distribution.
# 
# This file is part of REDHAWK socket_loopback_demo.
# 
# REDHAWK socket_loopback_demo is free software: you can redistribute it and/or modify it under
# the terms of the GNU Lesser General Public License as published by the Free
# Software Foundation, either version 3 of the License, or (at your option) any
# later version.
# 
# REDHAWK socket_loopback_demo is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
# A PARTICULAR PURPOSE.  See the GNU Lesser General Public License for more
# details.
# 
# You should have received a copy of the GNU Lesser General Public License along
# with this program.  If not, see http://www.gnu.org/licenses/.
###############################################################################

# RPM package for rh.socket_loopback_demo

%global _sdrroot /var/redhawk/sdr
%global _prefix %{_sdrroot}

Name: rh.socket_loopback_demo
Summary: Waveform rh.socket_loopback_demo
Version: 1.0.2
Release: 2%{?dist}
License: LGPLv3+
Group: REDHAWK/Waveforms
Source: %{name}-%{version}.tar.gz

# Require the controller whose SPD is referenced
Requires: rh.SigGen

# Require each referenced component
Requires: rh.SigGen rh.sinksocket rh.sourcesocket

BuildArch: noarch
BuildRoot: %{_tmppath}/%{name}-%{version}

%description
 * Commit: __REVISION__
 * Source Date/Time: __DATETIME__

%prep
%setup

%install
%__rm -rf $RPM_BUILD_ROOT
%__mkdir_p "$RPM_BUILD_ROOT%{_prefix}/dom/waveforms/rh/socket_loopback_demo"
%__install -m 644 socket_loopback_demo.sad.xml $RPM_BUILD_ROOT%{_prefix}/dom/waveforms/rh/socket_loopback_demo/socket_loopback_demo.sad.xml
%__install -m 644 socket_loopback_demo.sad_GDiagram $RPM_BUILD_ROOT%{_prefix}/dom/waveforms/rh/socket_loopback_demo/socket_loopback_demo.sad_GDiagram

%files
%defattr(-,redhawk,redhawk)
%dir %{_prefix}/dom/waveforms/rh
%dir %{_prefix}/dom/waveforms/rh/socket_loopback_demo
%{_prefix}/dom/waveforms/rh/socket_loopback_demo/socket_loopback_demo.sad.xml
%{_prefix}/dom/waveforms/rh/socket_loopback_demo/socket_loopback_demo.sad_GDiagram
