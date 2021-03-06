#!/usr/bin/python

import os
import sys
import random
import subprocess as sub
import getopt

def identity(x):
    return x

def cygpath(x):
    command = ["cygpath", "-wp", x]
    p = sub.Popen(command,stdout=sub.PIPE)
    output, errors = p.communicate()
    lines = output.split("\n")
    return lines[0]

if sys.platform == "cygwin":
    normclasspath = cygpath
else:
    normclasspath = identity

CONF_DIR = os.path.expanduser("~/.jstorm")
JSTORM_DIR = "/".join(os.path.realpath( __file__ ).split("/")[:-2])
JSTORM_CONF_DIR = os.getenv("JSTORM_CONF_DIR", JSTORM_DIR + "/conf" )
LOG4J_CONF = JSTORM_CONF_DIR + "/cluster.xml"
CONFIG_OPTS = []

def get_config_opts():
    global CONFIG_OPTS
    return "-Dstorm.options=" + (','.join(CONFIG_OPTS)).replace(' ', "%%%%")

if not os.path.exists(JSTORM_DIR + "/RELEASE"):
    print "******************************************"
    print "The jstorm client can only be run from within a release. You appear to be trying to run the client from a checkout of Storm's source code."
    print "\nYou can download a JStorm release "
    print "******************************************"
    sys.exit(1)  

def get_jars_full(adir):
    files = os.listdir(adir)
    ret = []
    for f in files:
        if f.endswith(".jar"):
            ret.append(adir + "/" + f)
    return ret

def get_classpath(extrajars):
    ret = []
    ret.extend(get_jars_full(JSTORM_DIR))
    ret.extend(get_jars_full(JSTORM_DIR + "/lib"))
    ret.extend(extrajars)
    return normclasspath(":".join(ret))

def confvalue(name, extrapaths):
    command = [
        "java", "-client", "-Xms512m", "-Xmx512m", get_config_opts(), "-cp", get_classpath(extrapaths), "backtype.storm.command.config_value", name
    ]
    p = sub.Popen(command, stdout=sub.PIPE)
    output, errors = p.communicate()
    lines = output.split("\n")
    for line in lines:
        tokens = line.split(" ")
        if tokens[0] == "VALUE:":
            return " ".join(tokens[1:])

def print_localconfvalue(name):
    """Syntax: [jstorm localconfvalue conf-name]

    Prints out the value for conf-name in the local Storm configs. 
    The local Storm configs are the ones in ~/.jstorm/storm.yaml merged 
    in with the configs in defaults.yaml.
    """
    print name + ": " + confvalue(name, [CONF_DIR])

def print_remoteconfvalue(name):
    """Syntax: [jstorm remoteconfvalue conf-name]

    Prints out the value for conf-name in the cluster's Storm configs. 
    The cluster's Storm configs are the ones in $STORM-PATH/conf/storm.yaml 
    merged in with the configs in defaults.yaml. 

    This command must be run on a cluster machine.
    """
    print name + ": " + confvalue(name, [JSTORM_CONF_DIR])

def exec_storm_class(klass, jvmtype="-server", childopts="", extrajars=[], args=[]):
    nativepath = confvalue("java.library.path", extrajars)
    args_str = " ".join(map(lambda s: "\"" + s + "\"", args))
    command = "java " + jvmtype + " -Djstorm.home=" + JSTORM_DIR + " " + get_config_opts() + " -Djava.library.path=" + nativepath + " " + childopts + " -cp " + get_classpath(extrajars) + " " + klass + " " + args_str
    print "Running: " + command    
    os.system(command)

def jar(jarfile, klass, *args):
    """Syntax: [jstorm jar topology-jar-path class ...]

    Runs the main method of class with the specified arguments. 
    The jstorm jars and configs in ~/.jstorm are put on the classpath. 
    The process is configured so that StormSubmitter 
    (http://nathanmarz.github.com/storm/doc/backtype/storm/StormSubmitter.html)
    will upload the jar at topology-jar-path when the topology is submitted.
    """
    childopts = "-Dstorm.jar=" + jarfile + (" -Dstorm.root.logger=INFO,stdout -Dlogback.configurationFile=%s/conf/aloha_logback.xml"  %JSTORM_DIR)
    #childopts = "-Dstorm.jar=" + jarfile
    exec_storm_class(
        klass,
        jvmtype="-client -Xms256m -Xmx256m",
        extrajars=[jarfile, CONF_DIR, JSTORM_DIR + "/bin", LOG4J_CONF],
        args=args,
        childopts=childopts)

def zktool(*args):
    """Syntax: [jstorm jar topology-jar-path class ...]

    Runs the main method of class with the specified arguments. 
    The jstorm jars and configs in ~/.jstorm are put on the classpath. 
    The process is configured so that StormSubmitter 
    (http://nathanmarz.github.com/storm/doc/backtype/storm/StormSubmitter.html)
    will upload the jar at topology-jar-path when the topology is submitted.
    """
    childopts = (" -Dstorm.root.logger=INFO,stdout -Dlogback.configurationFile=%s/conf/aloha_logback.xml"  %JSTORM_DIR)
    #childopts = " "
    exec_storm_class(
        "com.alibaba.jstorm.zk.ZkTool",
        jvmtype="-client -Xms256m -Xmx256m",
        extrajars=[ JSTORM_CONF_DIR],
        args=args,
        childopts=childopts)

def kill(*args):
    """Syntax: [jstorm kill topology-name [-w wait-time-secs]]

    Kills the topology with the name topology-name. Storm will 
    first deactivate the topology's spouts for the duration of 
    the topology's message timeout to allow all messages currently 
    being processed to finish processing. Storm will then shutdown 
    the workers and clean up their state. You can override the length 
    of time Storm waits between deactivation and shutdown with the -w flag.
    """
    childopts = (" -Dstorm.root.logger=INFO,stdout -Dlogback.configurationFile=%s/conf/aloha_logback.xml"  %JSTORM_DIR)
    #childopts = " "
    exec_storm_class(
        "backtype.storm.command.kill_topology", 
        args=args, 
        jvmtype="-client -Xms256m -Xmx256m", 
        extrajars=[CONF_DIR, JSTORM_DIR + "/bin", LOG4J_CONF],
        childopts=childopts)

def activate(*args):
    """Syntax: [jstorm activate topology-name]

    Activates the specified topology's spouts.
    """
    childopts = (" -Dstorm.root.logger=INFO,stdout -Dlogback.configurationFile=%s/conf/aloha_logback.xml"  %JSTORM_DIR)
    #childopts = " "
    exec_storm_class(
        "backtype.storm.command.activate", 
        args=args, 
        jvmtype="-client -Xms256m -Xmx256m", 
        extrajars=[CONF_DIR, JSTORM_DIR + "/bin", LOG4J_CONF],
        childopts=childopts)

def deactivate(*args):
    """Syntax: [jstorm deactivate topology-name]

    Deactivates the specified topology's spouts.
    """
    childopts = (" -Dstorm.root.logger=INFO,stdout -Dlogback.configurationFile=%s/conf/aloha_logback.xml"  %JSTORM_DIR)
    #childopts = " "
    exec_storm_class(
        "backtype.storm.command.deactivate", 
        args=args, 
        jvmtype="-client -Xms256m -Xmx256m", 
        extrajars=[CONF_DIR, JSTORM_DIR + "/bin", LOG4J_CONF],
        childopts=childopts)

def rebalance(*args):
    """Syntax: [jstorm rebalance topology-name [-w wait-time-secs]]

    Sometimes you may wish to spread out where the workers for a topology 
    are running. For example, let's say you have a 10 node cluster running 
    4 workers per node, and then let's say you add another 10 nodes to 
    the cluster. You may wish to have Storm spread out the workers for the 
    running topology so that each node runs 2 workers. One way to do this 
    is to kill the topology and resubmit it, but Storm provides a "rebalance" 
    command that provides an easier way to do this.

    Rebalance will first deactivate the topology for the duration of the 
    message timeout (overridable with the -w flag) and then redistribute 
    the workers evenly around the cluster. The topology will then return to 
    its previous state of activation (so a deactivated topology will still 
    be deactivated and an activated topology will go back to being activated).
    """
    childopts = (" -Dstorm.root.logger=INFO,stdout -Dlogback.configurationFile=%s/conf/aloha_logback.xml"  %JSTORM_DIR)
    #childopts = " "
    exec_storm_class(
        "backtype.storm.command.rebalance", 
        args=args, 
        jvmtype="-client -Xms256m -Xmx256m", 
        extrajars=[CONF_DIR, JSTORM_DIR + "/bin", LOG4J_CONF],
        childopts=childopts)


def nimbus():
    """Syntax: [jstorm nimbus]

    Launches the nimbus daemon. This command should be run under 
    supervision with a tool like daemontools or monit. 

    See Setting up a Storm cluster for more information.
    (https://github.com/nathanmarz/storm/wiki/Setting-up-a-Storm-cluster)
    """
    cppaths = [JSTORM_CONF_DIR]
    nimbus_classpath = confvalue("nimbus.classpath", cppaths)
    childopts = confvalue("nimbus.childopts", cppaths) + (" -Dlogfile.name=nimbus.log -Dlogback.configurationFile=%s/conf/cluster.xml "  %JSTORM_DIR)
    exec_storm_class(
        "com.alibaba.jstorm.daemon.nimbus.NimbusServer", 
        jvmtype="-server", 
        extrajars=(cppaths+[nimbus_classpath]), 
        childopts=childopts)

def supervisor():
    """Syntax: [jstorm supervisor]

    Launches the supervisor daemon. This command should be run 
    under supervision with a tool like daemontools or monit. 

    See Setting up a Storm cluster for more information.
    (https://github.com/nathanmarz/storm/wiki/Setting-up-a-Storm-cluster)
    """
    cppaths = [JSTORM_CONF_DIR]
    childopts = confvalue("supervisor.childopts", cppaths) + (" -Dlogfile.name=supervisor.log -Dlogback.configurationFile=%s/conf/cluster.xml "  %JSTORM_DIR)
    exec_storm_class(
        "com.alibaba.jstorm.daemon.supervisor.Supervisor", 
        jvmtype="-server", 
        extrajars=cppaths, 
        childopts=childopts)


def drpc():
    """Syntax: [jstorm drpc]

    Launches a DRPC daemon. This command should be run under supervision 
    with a tool like daemontools or monit. 

    See Distributed RPC for more information.
    (https://github.com/nathanmarz/storm/wiki/Distributed-RPC)
    """
    childopts = confvalue("supervisor.childopts", cppaths) + (" -Dlogfile.name=drpc.log -Dlogback.configurationFile=%s/conf/cluster.xml "  %JSTORM_DIR)
    exec_storm_class(
        "com.alibaba.jstorm.drpc.Drpc", 
        jvmtype="-server", 
        childopts=childopts, 
        extrajars=[JSTORM_CONF_DIR])

def print_classpath():
    """Syntax: [jstorm classpath]

    Prints the classpath used by the jstorm client when running commands.
    """
    print get_classpath([])

def print_commands():
    """Print all client commands and link to documentation"""
    print "Commands:\n\t",  "\n\t".join(sorted(COMMANDS.keys()))
    print "\nHelp:", "\n\thelp", "\n\thelp <command>"
    print "\nDocumentation for the jstorm client can be found at https://github.com/nathanmarz/storm/wiki/Command-line-client\n"

def print_usage(command=None):
    """Print one help message or list of available commands"""
    if command != None:
        if COMMANDS.has_key(command):
            print (COMMANDS[command].__doc__ or 
                  "No documentation provided for <%s>" % command)
        else:
           print "<%s> is not a valid command" % command
    else:
        print_commands()

def unknown_command(*args):
    print "Unknown command: [jstorm %s]" % ' '.join(sys.argv[1:])
    print_usage()

COMMANDS = {"jar": jar, "kill": kill, "nimbus": nimbus, "zktool": zktool,
            "drpc": drpc, "supervisor": supervisor, "localconfvalue": print_localconfvalue,
            "remoteconfvalue": print_remoteconfvalue, "classpath": print_classpath,
            "activate": activate, "deactivate": deactivate, "rebalance": rebalance, "help": print_usage}

def parse_config(config_list):
    global CONFIG_OPTS
    if len(config_list) > 0:
        for config in config_list:
            CONFIG_OPTS.append(config)

def parse_config_opts(args):
  curr = args[:]
  curr.reverse()
  config_list = []
  args_list = []
  
  while len(curr) > 0:
    token = curr.pop()
    if token == "-c":
      config_list.append(curr.pop())
    else:
      args_list.append(token)
  
  return config_list, args_list
    
def main():
    if len(sys.argv) <= 1:
        print_usage()
        sys.exit(-1)
    global CONFIG_OPTS
    config_list, args = parse_config_opts(sys.argv[1:])
    parse_config(config_list)
    COMMAND = args[0]
    ARGS = args[1:]
    (COMMANDS.get(COMMAND, "help"))(*ARGS)
    
if __name__ == "__main__":
    main()

