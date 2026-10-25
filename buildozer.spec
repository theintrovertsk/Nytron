[app]
title = Nytron
package.name = nytron
package.domain = org.nytron
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,json,txt,db
version = 1.1.0

requirements = hostpython3==3.11.6,python3==3.11.6,kivy==2.3.0,telethon,cryptography,pillow,pyaes,rsa,pyasn1,pyasn1-modules,sqlite3,openssl,android,jnius,pyjnius

orientation = portrait
fullscreen = 0
android.permissions = INTERNET,WRITE_EXTERNAL_STORAGE,READ_EXTERNAL_STORAGE,ACCESS_NETWORK_STATE
android.api = 33
android.minapi = 24
android.ndk = 25b
android.accept_sdk_license = True
android.archs = arm64-v8a
android.private_storage = True

[buildozer]
log_level = 2
warn_on_root = 0
