NAME	= eip712_implem

CC		= gcc

LIBP	= ./lib

WRAPP	= ./wrap

INC		= -I ./include

SRCP	= ./src_features/signMessageEIP712

SRC		= $(SRCP)/entrypoint.c \
		  $(SRCP)/mem.c \
		  $(SRCP)/encode_type.c \
		  $(SRCP)/type_hash.c \
		  $(SRCP)/context.c \
		  $(SRCP)/sol_typenames.c \
		  $(LIBP)/sha3.c \
		  $(SRCP)/mem_utils.c \
		  $(WRAPP)/libcxng.c \
		  $(WRAPP)/ctx.c \
		  $(SRCP)/encode_field.c \
		  $(SRCP)/field_hash.c \
		  $(SRCP)/path.c

INC		= -I $(LIBP) \
		  -I $(WRAPP)

OBJ		= $(SRC:.c=.o)

CFLAGS	= -Wall -Wextra $(INC)

DEBUG	:= 1

ifeq ($(DEBUG), 1)
CFLAGS	+= -O0 -g3 -DDEBUG
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
