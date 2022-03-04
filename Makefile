NAME	= eip712_implem

CC		= gcc

SRCP	= ./src_features/signMessageEIP712

SRC		= $(SRCP)/entrypoint.c

OBJ		= $(SRC:.c=.o)

CFLAGS	= -Wall -Wextra

DEBUG	:= 1

ifeq ($(DEBUG), 1)
CFLAGS	+= -O0 -g3
else
CFLAGS	+= -Os -g0
endif


all: 	$(NAME)

$(NAME):	$(OBJ)
		$(CC) $(CFLAGS) $(OBJ) -o $(NAME)

clean:
	rm -f $(OBJ)

fclean: clean
	rm -f $(NAME)

re:	fclean all
