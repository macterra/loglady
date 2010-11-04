#!/usr/bin/env python

from ircbot import SingleServerIRCBot
from irclib import nm_to_n, nm_to_uh, irc_lower, DEBUG
import string, time, re, random
import MySQLdb

NEW_LOG = "INSERT INTO irclog (logged, event, source, target, text, status) VALUES (NOW(), '%s', '%s', '%s', '%s', 0)"
LAST_LOG = "SELECT logged, event, source, text FROM irclog WHERE target='%s' ORDER BY logged DESC LIMIT %d"
GET_REP = "SELECT r.* FROM cov_reputation r, cov_irc_nicks n where r.id_member=n.id_member and n.nick='%s'"

db = MySQLdb.connect(db='yabbse', user='root')
dbc = db.cursor()

class LogLadyBot(SingleServerIRCBot):
    def __init__(self, channel, nickname, server, port=6667):
        SingleServerIRCBot.__init__(self, [(server, port)], nickname, nickname)
        self.nickname = nickname
        self.channel = channel
        self.history = {}
        self.start()

    def get_version(self):
        """Returns the bot version.
        Used when answering a CTCP VERSION request.
        """
        return "VERSION LogLadyBot by David Lucifer <david@lucifer.com>"
    
    def delay(self):
        time.sleep(random.randrange(2,5))
    
    def on_welcome(self, c, e):
        if (self.channel != None):
            c.join(self.channel)
        
    def on_invite(self, c, e):
        channel = e.arguments()[0]
        c.join(channel)

    def getRep(self, nick):
        sql = GET_REP % nick
        if DEBUG: print sql
        dbc.execute(sql)
        rows = dbc.fetchall()
        print rows
        print len(rows)
        if (len(rows) == 1):
            rep = rows[0][1]
            act = rows[0][2]
            inf = rows[0][3]
            equ = rows[0][4]
            reply = "%s's Meridion stats: reputation:%.4f activity:%.4f influence:%.2f equity:%.2f%%" % (nick, rep, act, inf, equ)
        else:
            reply = "%s doesn't have a reputation yet" % nick
        return reply
        
    def writeLog(self, type, source, target, msg):
        con = MySQLdb.connect(db='yabbse', user='root')
        cur = con.cursor()
        sql = NEW_LOG % (type, source, target, db.escape_string(msg))
        if DEBUG: print sql
        cur.execute(sql)

        now = time.time()
        now = time.localtime(now)
        now = time.strftime("[%H:%M]", now)
        if type == 'pubmsg':
            nick = nm_to_n(source)
            line = "%s <%s> %s" % (now, nick, msg)
        else:
            line = "%s %s" % (now, msg)
        if self.history.has_key(target):
            chanhist = self.history[target]
        else:
            chanhist = []
            self.history[target] = chanhist
        chanhist.append(line)
        while len(chanhist)>100:
            chanhist.pop(0)
        if DEBUG: print line
        
    def lastLog(self, target, count):
	reply = "last %d lines in %s...\n" % (count, target)
	if self.history.has_key(target):
	    lines = self.history[target][-count:]
	else:
	    lines = []
	for line in lines:
	    reply = reply + line + "\n"
        reply = reply + "done\n"
	return reply

    def lastLogOld(self, target, count):
        sql = LAST_LOG % (target, count)
        if DEBUG: print sql
        dbc.execute(sql)
        rows = dbc.fetchall()
        reply = ""
        for row in rows:
            logged = row[0]
            event = row[1]
            source = row[2]
            nick = nm_to_n(source)
            text = row[3]
            if event == 'pubmsg':
                line = "[%02d:%02d] <%s> %s" % (logged.hour, logged.minute, nick, text)
            else:
                line = "[%02d:%02d] %s" % (logged.hour, logged.minute, text)
            if DEBUG: print line
            reply = line + "\n" + reply
        return reply
    
    def on_topic(self,c,e):
        args = e.arguments()
        source = e.source()
        nick = nm_to_n(source)
        channel = e.target()
        if self.is_listening(channel):
            msg = "%s has changed the topic on %s to \"%s\"" % (nick, channel, args[0])
            self.writeLog("topic", source, channel, msg)
        
    def on_mode(self,c,e):
        args = e.arguments()
        source = e.source()
        nick = nm_to_n(source)
        channel = e.target()
        if self.is_listening(channel):
            msg = "Mode change [%s] on %s by %s" % (string.join(args), channel, nick)
            self.writeLog("mode", source, channel, msg)
        
    def on_join(self,c,e):
        source = e.source()
        nick = nm_to_n(source)
        rest = nm_to_uh(source)
        channel = e.target()
        if self.is_listening(channel):
            msg = "%s (%s) has joined %s" % (nick, rest, channel)
            self.writeLog("join", source, channel, msg)
        
    def on_part(self,c,e):
        source = e.source()
        nick = nm_to_n(source)
        rest = nm_to_uh(source)
        channel = e.target()
        if self.is_listening(channel):
            msg = "%s (%s) has left %s" % (nick, rest, channel)
            self.writeLog("part", source, channel, msg)
        
    def on_quit(self,c,e):
        args = e.arguments()
        source = e.source()
        nick = nm_to_n(source)
        rest = nm_to_uh(source)
        msg = "%s (%s) has quit IRC [%s]" % (nick, rest, args[0])
        for channel in self.channels.keys():
            if self.is_listening(channel) and nick in self.channels[channel].users():
                self.writeLog("quit", source, channel, msg)
        
    def on_kick(self,c,e):
        args = e.arguments()
        source = e.source()
        nick = nm_to_n(source)
        channel = e.target()
        if self.is_listening(channel):
            msg = "%s has kicked %s from %s [%s]" % (nick, args[0], channel, args[1])
            self.writeLog("kick", source, channel, msg)
        
    def on_nick(self, c, e):
        nick = nm_to_n(e.source())
        newnick = e.target()
        msg = "%s is now known as %s" % (nick, newnick)
        for channel in self.channels.keys():
            if self.is_listening(channel) and nick in self.channels[channel].users():
                self.writeLog("nick", e.source(), channel, msg)
        
    def on_privmsg(self, c, e):
        args = e.arguments()
        msg = args[0]
        nick = nm_to_n(e.source())
        channel = e.target()
        
        self.writeLog("privmsg", e.source(), e.target(), msg)
        
        output = self.do_command(c, nick, channel, msg)
        if output != None:
            self.privmsg_multiline(c,nick,output)

    def on_pubmsg(self, c, e):
        args = e.arguments()
        msg = irc_lower(args[0])
        channel = e.target()
        source = nm_to_n(e.source())
        mynick = irc_lower(c.get_nickname())
        
        if self.is_listening(channel):
            self.writeLog("pubmsg", e.source(), e.target(), args[0])
        
            
    def on_ctcp(self, c, e):
        args = e.arguments()
        type = args[0]
        
        if type == 'ACTION':
            nick = nm_to_n(e.source())
            channel = e.target()
            if self.is_listening(channel):
                if len(args) > 1:
                    msg = nick + " " + args[1]
                else:
                    msg = nick
                self.writeLog("action", e.source(), channel, msg)
        else:
            return SingleServerIRCBot.on_ctcp(self, c, e)                          
        
    def notice_multiline(self,c,channel,msg):
        for x in string.split(msg,"\n"):
            c.notice(channel, x)
            time.sleep(1)
            
    def privmsg_multiline(self,c,nick,msg):
        for x in string.split(msg,"\n"):
            c.privmsg(nick, x)
            time.sleep(1)

    def is_listening(self, channel):
        mynick = self.connection.get_nickname()
        return self.channels.has_key(channel) and self.channels[channel].is_voiced(mynick)
    
    def do_command(self, c, nick, channel, cmd):
        masters = ["Lucifer", "LuciferAFK", "Hermit", "Eliezer"]
        
	try:
	    cmd, args = string.split(cmd, None, 1)
	except:
	    args = ""

        if cmd == "die" and nick in masters:
	    for chan in self.channels.keys():
		c.privmsg(chan, "Oh my goodness!")
            self.die()
	elif cmd == "which":
	    return str(self.channels.keys())
        elif cmd == "who":
            if (self.channels.has_key(args)):
                return str(self.channels[args].users())
            else:
                return "I'm not on channel: " + args
        elif cmd == "part" or cmd == "depart" or cmd == "leave":
            if (self.channels.has_key(args)):
		c.privmsg(args, "A lady knows when she's not welcome.")
                self.connection.part(args)
            else:
                return "I'm not on channel: " + args
	elif cmd == "help":
	    if args == "die":
		return "I will commit hara-kiri"
	    elif args == "which":
		return "I will tell you which channels I'm on"
	    elif args == "who":
		return "I will tell you who is on the specified channel"
	    elif args in ["part", "depart", "leave"]:
		return "I will leave the specified channel"
	    else:
		return "I understand [die, which, who, part, replay, link, help]"
	elif cmd == "say" and nick in masters:
	    try:
		channel, msg = string.split(args, None, 1)
		c.privmsg(channel, msg)
	    except:
		return "Say what where?"
        elif cmd == "replay":
            try:
                channel, count = string.split(args)
                count = string.atoi(count)
                max = 20
                if (count > max):
                    count = max
                    c.privmsg(nick, "I will replay %d lines max" % max)
                c.privmsg(nick, 'One moment please...')
                return self.lastLog(channel, count)
            except:
                return "replay <channel> <count>"
        elif cmd == "rep":
            try:
                nick = string.lower(args)
                return self.getRep(nick)
            except:
                return "rep nick"
        elif cmd == "url" or cmd == "link":
            try:
                channel, count = string.split(args)
                count = string.atoi(count)
                c.privmsg(nick, "You can view the last %d minutes of %s here>>" % (count, channel))
                mark = time.localtime(time.time() - count*60)
                spec = time.strftime("date=%Y-%m-%d;time=%H:%M", mark)
		if (channel[0] != "#"):
		    channel = "#" + channel
		channel = re.sub("#", "%23", channel)
                url = "http://virus.lucifer.com/bbs/index.php?board=;action=chatlog2;channel=%s;%s" % (channel, spec)
                c.privmsg(nick, url)
            except:
                return "url #<channel> <minutes>"
        else:
            return "I don't understand: " + cmd

def main():
    import sys
    import getopt
    args = sys.argv[1:]
    optlist, args = getopt.getopt(args,'s:p:c:n:h')
    port = 6667

    channel = '#bot'
    nickname = 'LogLady'
    server = 'localhost'

    for o in optlist:
        name = o[0]
        value = o[1]
        if name == '-s':
            server = value
        elif name == '-p':
            try:
                port = int(value)
            except ValueError:
                print "Error: Erroneous port."
                sys.exit(1)
        elif name == '-c':
            channel = value
        elif name == '-n':
            nickname = value

    if(channel != '' and nickname != '' and server != ''):
        bot = LogLadyBot(channel, nickname, server, port)
        bot.start()
	print "exiting normally"
    else:
        print "Commandline options:"
        print
        print "  -s server"
        print "  [-p port]"
        print "  -n nick"
        print "  -c channel"
        print

if __name__ == "__main__":
    main()
