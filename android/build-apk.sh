#!/bin/bash
set -euo pipefail
android_dir="$(cd "$(dirname "$0")" && pwd)"
planner_dir="$(dirname "$android_dir")"
toolchain_dir="${PLANWISE_ANDROID_TOOLS:-/private/tmp/planwise-android-toolchain}"
export JAVA_HOME="${JAVA_HOME:-$toolchain_dir/jdk/Contents/Home}"
export ANDROID_HOME="${ANDROID_HOME:-$toolchain_dir/sdk}"
export GRADLE_USER_HOME="${GRADLE_USER_HOME:-$toolchain_dir/gradle}"
export PATH="$JAVA_HOME/bin:$PATH"
for name in planner.py storage.py timetable.py events.py time_slots.py validation.py holidays.py i18n.py translations.json; do
    cp "$planner_dir/$name" "$android_dir/app/src/main/python/$name"
done
for name in main.py style.css app.js; do
    cp "$android_dir/runtime/$name" "$android_dir/app/src/main/python/$name"
done
printf 'sdk.dir=%s\n' "$ANDROID_HOME" > "$android_dir/local.properties"
cd "$android_dir"
bash ./gradlew --no-daemon --console=plain assembleDebug
mkdir -p "$planner_dir/output/android"
cp app/build/outputs/apk/debug/app-debug.apk "$planner_dir/output/android/Planwise-Local-0.5.2-preview.apk"
"$ANDROID_HOME/build-tools/36.0.0/apksigner" verify --verbose "$planner_dir/output/android/Planwise-Local-0.5.2-preview.apk"
"$ANDROID_HOME/build-tools/36.0.0/zipalign" -c -P 16 4 "$planner_dir/output/android/Planwise-Local-0.5.2-preview.apk"
shasum -a 256 "$planner_dir/output/android/Planwise-Local-0.5.2-preview.apk"
