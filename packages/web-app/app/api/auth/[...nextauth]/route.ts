import NextAuth from "next-auth";
import GoogleProvider from "next-auth/providers/google";
import CredentialsProvider from "next-auth/providers/credentials";
import type { NextAuthOptions } from "next-auth";
import { createUserCommand, CreateUserData, getUserByEmail, User, UserModel } from "@core/index";

const providers: NextAuthOptions['providers'] = [
    GoogleProvider({
        clientId: process.env.GOOGLE_CLIENT_ID!,
        clientSecret: process.env.GOOGLE_CLIENT_SECRET!,
    }),
];

if (process.env.NODE_ENV === 'development') {
    providers.push(
        CredentialsProvider({
            name: 'Credentials',
            credentials: {
                email: { label: "Email", type: "text" },
                password: { label: "Password", type: "password" }
            },
            async authorize(credentials, req) {
                const testEmail = process.env.TEST_EMAIL;
                const testPassword = process.env.TEST_PASSWORD;

                if (testEmail && testPassword && credentials?.email === testEmail && credentials?.password === testPassword) {
                    // Ensure we return a user object that matches what NextAuth expects
                    // and what our app expects (email is crucial)
                    return {
                        id: "test-user",
                        name: "Test User",
                        email: testEmail,
                        image: null
                    };
                }
                return null;
            }
        })
    );
}

export const authOptions: NextAuthOptions = {
    providers,
    callbacks: {
        async signIn({ user, account }) {
            // Allow credentials login to bypass database check if needed, 
            // OR ensure the test user exists in the DB.
            // For now, let's allow it to proceed to user creation logic.

            if (account?.provider === 'credentials') {
                // For test user, we need to ensure they exist in DB so page.tsx doesn't redirect
                const currentUser = await getUserByEmail(user.email!);
                if (!currentUser) {
                    const userData: CreateUserData = {
                        name: user.name || 'Test User',
                        email: user.email!,
                        level: 'A1',
                    }
                    try {
                        await createUserCommand(userData);
                    } catch (err) {
                        console.error('Error creating test user:', err);
                        return false;
                    }
                }
                return true;
            }

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
