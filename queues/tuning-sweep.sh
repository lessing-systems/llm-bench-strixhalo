# Tuning sweep for a winning config W (default swift-iq3s). Run with: W=<config> scripts/run.sh queues/tuning-sweep.sh
W=${W:-swift-iq3s}
speed $W "MTPN=2"                 $W-mtp2
speed $W "MTPN=3"                 $W-mtp3
speed $W "MTPN=3;PMIN=0.3"        $W-mtp3-p03
speed $W "MTPN=4;PMIN=0.5"        $W-mtp4-p05
speed $W "MTPN=2;SPECTYPE=draft-mtp,ngram-mod" $W-mtp2-ngram
speed $W "MTPN=2"                 $W-mtp2-ub256 "-ub 256"
evalr $W $W --only code --repeat 4
