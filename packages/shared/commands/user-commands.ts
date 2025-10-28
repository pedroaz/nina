import { UserModel } from "../entities/user";

export interface CreateUserData {
    name: string;
    email: string;
}

export async function createUserCommand(userData: CreateUserData) {
    const user = new UserModel(userData);
    await user.save();
}