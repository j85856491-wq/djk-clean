[app]
title = DJK Cleaner
package.name = djkcleaner
package.domain = com.tondomaine
source.dir = .
version = 1.0
requirements = python3,kivy==2.3.1
orientation = portrait

android.minapi = 21          # couvre Android 5.0+
android.api = 34             # cible la dernière API (obligatoire pour publication Play Store)
android.ndk_api = 21
android.archs = arm64-v8a, armeabi-v7a
android.permissions = READ_MEDIA_IMAGES, READ_MEDIA_VIDEO, MANAGE_EXTERNAL_STORAGE
android.enable_androidx = True
android.accept_sdk_license = True
