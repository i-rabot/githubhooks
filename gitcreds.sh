# git passes a prompt as first argument
if echo "$1" | fgrep -qi user
then
	echo "$GITUSER"
else
	echo "$GITPASS"
fi
