#!/bin/sh
# Renew the robot certificate from the Kerberos keytab.
set -e
X509_USER_CERT="$HOME/.globus/usercert.pem"
X509_USER_KEY="$HOME/.globus/userkey.pem"
KERBEROS_KEYTAB="${HOME}/.globus/krb5.keytab"
KERBEROS_PRINCIPAL="$(klist -k "${KERBEROS_KEYTAB}" | tail -n 1 | sed 's/.*\s//')"
kinit "${KERBEROS_PRINCIPAL}" -k -t "${KERBEROS_KEYTAB}"
ligo-proxy-init -k
GRID_PROXY_PATH="${grid-proxy-info -path}"
cp "${GRID_PROXY_PATH}" "${X509_USER_CERT}"
cp "${GRID_PROXY_PATH}" "${X509_USER_KEY}"
