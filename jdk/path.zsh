# JDK configuration

# IntelliJ IDEA bundled JDK
if [ -d "$HOME/Applications/IntelliJ IDEA.app/Contents/jbr/Contents/Home" ]; then
  export JAVA_HOME="$HOME/Applications/IntelliJ IDEA.app/Contents/jbr/Contents/Home"
  export PATH="$JAVA_HOME/bin:$PATH"
fi
