import NextAuth from "next-auth";
import GoogleProvider from "next-auth/providers/google";
import type { NextAuthOptions } from "next-auth";
import { createUserCommand, CreateUserData, getUserByEmail, User, UserModel } from "@core/index";

export const authOptions: NextAuthOptions = {
    providers: [
        GoogleProvider({
            clientId: process.env.GOOGLE_CLIENT_ID!,
            clientSecret: process.env.GOOGLE_CLIENT_SECRET!,
        }),
    ],
    callbacks: {
        async signIn({ user }) {
            if (!user.email) {
                return false;
            }

            const currentUser = await getUserByEmail(user.email);

            if (!currentUser) {
                const userData: CreateUserData = {
                    name: user.name || 'No Name',
                    email: user.email,
                    level: 'A1',
                }

                try {
                    await createUserCommand(userData);
                } catch (err) {
                    console.error('Error creating user:', err);
                    // Block sign in if user creation fails to prevent orphaned auth sessions
                    return false;
                }
            }

            return true;
        },
    },
};

const handler = NextAuth(authOptions);

export { handler as GET, handler as POST };
